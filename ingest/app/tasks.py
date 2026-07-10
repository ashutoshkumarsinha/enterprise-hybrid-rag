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
    """Validate and accept chunk payloads; store write path remains stub."""
    from app.telemetry import get_tracer

    payload = chunks or []
    with get_tracer().start_as_current_span("ingest.batch_write") as span:
        count = len(payload)
        span.set_attribute("ingest.chunk_count", count)
        span.set_attribute("module_id", "hybrid-rag-ingest")
        validated = 0
        for chunk in payload:
            if chunk.get("uuid") and chunk.get("text"):
                validated += 1
        write_stub = os.environ.get("INGEST_WRITE_STUB", "true").lower() in ("true", "1", "yes")
        return {
            "written": validated if not write_stub else 0,
            "validated": validated,
            "stub": write_stub,
        }
