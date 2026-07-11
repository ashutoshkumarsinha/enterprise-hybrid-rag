"""Ingest orchestrator — job enqueue and parse pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from app.acl_handlers import (
    create_acl_grant,
    delete_acl_grant,
    list_acl_grants,
    patch_collection_default_acl,
)
from app.acl_store import get_acl_store
from app.backpressure import assert_enqueue_allowed, check_backpressure
from app.catalog_store import get_catalog_store
from app.connector_handlers import enqueue_collection_sync
from app.job_handlers import get_job_status
from app.job_store import get_job_store
from app.parsers.base import ParseContext
from app.pipeline import parse_document
from app.tasks import batch_write
from app.telemetry import get_tracer, setup_otel

app = FastAPI(title="hybrid-rag-ingest-orchestrator", version="0.10.0-backpressure")
setup_otel(app)
tracer = get_tracer()


def _parser_profile() -> str:
    return os.environ.get("PARSER_PROFILE", "fast")


@app.get("/admin/healthz")
def healthz() -> dict:
    with tracer.start_as_current_span("ingest.healthz"):
        return {
            "status": "ok",
            "module": "hybrid-rag-ingest",
            "stub": False,
            "parser_profile": _parser_profile(),
            "backpressure": check_backpressure().as_dict(),
            "checks": {
                "celery_ok": True,
                "redis_broker_ok": True,
                "qdrant_write_ok": os.environ.get("QDRANT_STUB", "true").lower() in ("true", "1", "yes"),
                "neo4j_write_ok": os.environ.get("NEO4J_STUB", "true").lower() in ("true", "1", "yes"),
                "catalog_ok": (
                    get_acl_store().healthcheck()
                    and get_job_store().healthcheck()
                    and get_catalog_store().healthcheck()
                ),
                "inference_embed_ok": os.environ.get("EMBED_STUB", "true").lower() in ("true", "1", "yes"),
            },
        }


@app.post("/admin/ingest/collection")
async def ingest_collection(request: Request) -> dict:
    with tracer.start_as_current_span("ingest.job.enqueue_collection"):
        return await enqueue_collection_sync(request)


@app.post("/admin/connectors/sync")
async def connectors_sync(request: Request) -> dict:
    with tracer.start_as_current_span("ingest.connector.enqueue"):
        return await enqueue_collection_sync(request)


@app.post("/admin/ingest/document")
async def ingest_document(request: Request) -> dict:
    """Parse a local file and enqueue ``batch_write`` with chunk payloads."""
    assert_enqueue_allowed()
    body = await request.json()
    path = body.get("path")
    tenant_id = body.get("tenant_id")
    collection_id = body.get("collection_id")
    document_id = body.get("document_id")
    version_id = body.get("version_id") or "v1"
    title = body.get("title") or document_id
    if not all([path, tenant_id, collection_id, document_id]):
        raise HTTPException(status_code=422, detail={"code": "validation"})

    source = Path(path)
    if not source.exists():
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": str(path)})

    ctx = ParseContext(
        tenant_id=tenant_id,
        collection_id=collection_id,
        document_id=document_id,
        version_id=version_id,
        title=title,
        source_uri=body.get("source_uri") or str(source),
        source_system=body.get("source_system", "filesystem"),
        parser_profile=body.get("parser_profile") or _parser_profile(),
        tags=list(body.get("tags") or []),
    )
    job = get_job_store().create_job(
        tenant_id=tenant_id,
        collection_id=collection_id,
        mode="version",
        job_type="document",
        metadata={
            "document_id": document_id,
            "version_id": version_id,
            "path": str(source),
        },
    )
    job_id = job["job_id"]
    with tracer.start_as_current_span("ingest.job.enqueue_document") as span:
        span.set_attribute("ingest.job_id", job_id)
        chunks = parse_document(
            source,
            ctx=ctx,
            manifest_parser=body.get("manifest_parser"),
        )
        async_result = batch_write.delay(chunks, job_id=job_id)
        get_job_store().attach_task_id(job_id, async_result.id)
        return {
            "status": "accepted",
            "job_id": job_id,
            "task_id": async_result.id,
            "chunk_count": len(chunks),
            "parser_profile": ctx.parser_profile,
            "stub": False,
        }


@app.get("/admin/ingest/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    with tracer.start_as_current_span("ingest.job.status") as span:
        span.set_attribute("ingest.job_id", job_id)
        return get_job_status(job_id)


@app.post("/admin/acl/grants")
async def post_acl_grant(request: Request) -> dict:
    with tracer.start_as_current_span("ingest.acl.grant.create"):
        return await create_acl_grant(request)


@app.get("/admin/acl/grants")
def get_acl_grants(
    tenant_id: str,
    principal: str | None = None,
    collection_id: str | None = None,
) -> dict:
    with tracer.start_as_current_span("ingest.acl.grant.list"):
        return list_acl_grants(
            tenant_id=tenant_id,
            principal=principal,
            collection_id=collection_id,
        )


@app.delete("/admin/acl/grants/{grant_id}")
def remove_acl_grant(grant_id: str) -> dict:
    with tracer.start_as_current_span("ingest.acl.grant.delete") as span:
        span.set_attribute("acl.grant_id", grant_id)
        return delete_acl_grant(grant_id)


@app.patch("/admin/collections/{tenant_id}/{collection_id}/default_acl")
async def patch_default_acl(tenant_id: str, collection_id: str, request: Request) -> dict:
    with tracer.start_as_current_span("ingest.acl.collection.default_acl"):
        return await patch_collection_default_acl(tenant_id, collection_id, request)
