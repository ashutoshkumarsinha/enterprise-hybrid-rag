"""Celery app stub for hybrid-rag-ingest workers."""

from __future__ import annotations

import os

from celery import Celery

from app.langsmith_config import setup_langsmith
from app.telemetry import setup_otel

broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")

celery_app = Celery("hybrid-rag-ingest", broker=broker, include=["app.tasks"])
setup_otel()
setup_langsmith()


@celery_app.task(name="ingest.batch_write")
def batch_write(chunks: list | None = None) -> dict:
    """Stub — implement parse → embed → Qdrant/Neo4j write."""
    from app.telemetry import get_tracer

    with get_tracer().start_as_current_span("ingest.batch_write") as span:
        count = len(chunks or [])
        span.set_attribute("ingest.chunk_count", count)
        span.set_attribute("module_id", "hybrid-rag-ingest")
        return {"written": count, "stub": True}
