"""Celery app for hybrid-rag-ingest workers."""

from __future__ import annotations

import os

from celery import Celery

from app.connector_sync import sync_collection
from app.beat_config import beat_enabled, build_beat_schedule, load_beat_targets
from app.connector_enqueue import enqueue_connector_sync
from app.langsmith_config import setup_langsmith
from app.task_jobs import on_task_failure, on_task_start, on_task_success
from app.telemetry import setup_otel
from app.writers import write_chunks

broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")

celery_app = Celery("hybrid-rag-ingest", broker=broker, include=["app.tasks"])
celery_app.conf.beat_schedule = build_beat_schedule()
setup_otel()
setup_langsmith()


@celery_app.task(name="ingest.batch_write")
def batch_write(chunks: list | None = None, job_id: str | None = None) -> dict:
    """Validate, embed, and upsert chunk payloads to Qdrant + Neo4j."""
    from app.telemetry import get_tracer

    payload = chunks or []
    on_task_start(job_id)
    try:
        with get_tracer().start_as_current_span("ingest.batch_write") as span:
            span.set_attribute("ingest.chunk_count", len(payload))
            span.set_attribute("module_id", "hybrid-rag-ingest")
            if job_id:
                span.set_attribute("ingest.job_id", job_id)
            result = write_chunks(payload, job_id=job_id)
            span.set_attribute("ingest.written", result.get("written", 0))
            span.set_attribute("ingest.validated", result.get("validated", 0))
            span.set_attribute("ingest.skipped_dedup", result.get("skipped_dedup", 0))
        on_task_success(job_id, result)
        return result
    except Exception as exc:
        on_task_failure(job_id, exc)
        raise


@celery_app.task(name="ingest.connector_sync")
def connector_sync(payload: dict | None = None) -> dict:
    """Celery entrypoint for connector collection sync."""
    from app.telemetry import get_tracer

    body = payload or {}
    job_id = body.get("job_id")
    on_task_start(job_id)
    try:
        with get_tracer().start_as_current_span("ingest.connector_sync") as span:
            span.set_attribute("module_id", "hybrid-rag-ingest")
            if job_id:
                span.set_attribute("ingest.job_id", job_id)
            result = sync_collection(
                tenant_id=body["tenant_id"],
                collection_id=body["collection_id"],
                version_id=body.get("version_id", "v1"),
                connector=body.get("connector", "s3"),
                prefix=body.get("prefix"),
                mode=body.get("mode", "incremental"),
                since=body.get("since"),
                parser_profile=body.get("parser_profile"),
                job_id=job_id,
            )
            span.set_attribute("ingest.ingested", result.get("ingested", 0))
            span.set_attribute("ingest.skipped", result.get("skipped", 0))
        on_task_success(job_id, result)
        return result
    except Exception as exc:
        on_task_failure(job_id, exc)
        raise


@celery_app.task(name="ingest.scheduled_connector_sync")
def scheduled_connector_sync() -> dict:
    """Beat tick — enqueue connector sync for configured collection targets."""
    from app.telemetry import get_tracer

    if not beat_enabled():
        return {"enqueued": 0, "skipped": True, "reason": "beat_disabled"}
    targets = load_beat_targets()
    if not targets:
        return {"enqueued": 0, "skipped": True, "reason": "no_targets"}

    jobs: list[dict] = []
    with get_tracer().start_as_current_span("ingest.beat.connector_sync") as span:
        span.set_attribute("ingest.target_count", len(targets))
        for target in targets:
            body = {**target, "scheduled": True}
            jobs.append(enqueue_connector_sync(body))
        span.set_attribute("ingest.enqueued", len(jobs))
    return {"enqueued": len(jobs), "jobs": jobs, "stub": False}
