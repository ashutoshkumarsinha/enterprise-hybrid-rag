"""Ingest job status HTTP handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.job_store import get_job_store


def get_job_status(job_id: str) -> dict[str, Any]:
    job = get_job_store().get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "not_found", "job_id": job_id})
    return job
