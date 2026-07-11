"""Celery app for hybrid-rag-ingest workers."""

from __future__ import annotations

import os

from celery import Celery

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
        return result
