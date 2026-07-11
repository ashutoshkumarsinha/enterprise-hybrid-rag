"""Celery app for hybrid-rag-ingest workers."""

from __future__ import annotations

import os

from celery import Celery

from app.connector_sync import sync_collection
from app.langsmith_config import setup_langsmith
from app.telemetry import setup_otel
from app.writers import write_chunks

broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")

celery_app = Celery("hybrid-rag-ingest", broker=broker, include=["app.tasks"])
setup_otel()
setup_langsmith()


@celery_app.task(name="ingest.batch_write")
def batch_write(chunks: list | None = None) -> dict:
    """Validate, embed, and upsert chunk payloads to Qdrant + Neo4j."""
    from app.telemetry import get_tracer

    payload = chunks or []
    with get_tracer().start_as_current_span("ingest.batch_write") as span:
        span.set_attribute("ingest.chunk_count", len(payload))
        span.set_attribute("module_id", "hybrid-rag-ingest")
        result = write_chunks(payload)
        span.set_attribute("ingest.written", result.get("written", 0))
        span.set_attribute("ingest.validated", result.get("validated", 0))
        span.set_attribute("ingest.skipped_dedup", result.get("skipped_dedup", 0))
        return result


@celery_app.task(name="ingest.connector_sync")
def connector_sync(payload: dict | None = None) -> dict:
    """Celery entrypoint for connector collection sync."""
    from app.telemetry import get_tracer

    body = payload or {}
    with get_tracer().start_as_current_span("ingest.connector_sync") as span:
        span.set_attribute("module_id", "hybrid-rag-ingest")
        result = sync_collection(
            tenant_id=body["tenant_id"],
            collection_id=body["collection_id"],
            version_id=body.get("version_id", "v1"),
            connector=body.get("connector", "s3"),
            prefix=body.get("prefix"),
            mode=body.get("mode", "incremental"),
            since=body.get("since"),
            parser_profile=body.get("parser_profile"),
        )
        span.set_attribute("ingest.ingested", result.get("ingested", 0))
        span.set_attribute("ingest.skipped", result.get("skipped", 0))
        return result
