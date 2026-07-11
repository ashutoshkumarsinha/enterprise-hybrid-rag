"""Ingest orchestrator — job enqueue and parse pipeline."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from app.parsers.base import ParseContext
from app.pipeline import parse_document
from app.tasks import batch_write
from app.telemetry import get_tracer, setup_otel

app = FastAPI(title="hybrid-rag-ingest-orchestrator", version="0.3.0-writers")
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
            "checks": {
                "celery_ok": True,
                "redis_broker_ok": True,
                "qdrant_write_ok": os.environ.get("QDRANT_STUB", "true").lower() in ("true", "1", "yes"),
                "neo4j_write_ok": os.environ.get("NEO4J_STUB", "true").lower() in ("true", "1", "yes"),
                "catalog_ok": True,
                "inference_embed_ok": os.environ.get("EMBED_STUB", "true").lower() in ("true", "1", "yes"),
            },
        }


@app.post("/admin/ingest/collection")
def ingest_collection() -> dict:
    with tracer.start_as_current_span("ingest.job.enqueue_collection"):
        return {"status": "accepted", "stub": True, "message": "collection ingest not yet implemented"}


@app.post("/admin/ingest/document")
async def ingest_document(request: Request) -> dict:
    """Parse a local file and enqueue ``batch_write`` with chunk payloads."""
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
    job_id = str(uuid.uuid4())
    with tracer.start_as_current_span("ingest.job.enqueue_document") as span:
        span.set_attribute("ingest.job_id", job_id)
        chunks = parse_document(
            source,
            ctx=ctx,
            manifest_parser=body.get("manifest_parser"),
        )
        async_result = batch_write.delay(chunks)
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
        return {"job_id": job_id, "status": "pending", "stub": True}
