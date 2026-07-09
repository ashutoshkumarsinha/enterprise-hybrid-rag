"""Minimal orchestrator stub for hybrid-rag-ingest compose health checks.

Replace with full orchestrator.py, pipeline.py, and admin routes in implementation.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from app.telemetry import get_tracer, setup_otel

app = FastAPI(title="hybrid-rag-ingest-orchestrator", version="0.1.0-stub")
setup_otel(app)
tracer = get_tracer()


@app.get("/admin/healthz")
def healthz() -> dict:
    with tracer.start_as_current_span("ingest.healthz"):
        return {
            "status": "ok",
            "module": "hybrid-rag-ingest",
            "stub": True,
            "checks": {
                "celery_ok": True,
                "redis_broker_ok": True,
                "qdrant_write_ok": True,
                "neo4j_write_ok": True,
                "catalog_ok": True,
                "inference_embed_ok": True,
            },
        }


@app.post("/admin/ingest/collection")
def ingest_collection() -> dict:
    with tracer.start_as_current_span("ingest.job.enqueue_collection"):
        return {"status": "accepted", "stub": True, "message": "implement orchestrator.enqueue_collection"}


@app.post("/admin/ingest/document")
def ingest_document() -> dict:
    with tracer.start_as_current_span("ingest.job.enqueue_document"):
        return {"status": "accepted", "stub": True, "message": "implement orchestrator.enqueue_document"}


@app.get("/admin/ingest/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    with tracer.start_as_current_span("ingest.job.status") as span:
        span.set_attribute("ingest.job_id", job_id)
        return {"job_id": job_id, "status": "pending", "stub": True}
