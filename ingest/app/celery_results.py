"""Reconcile catalog job rows with Celery result backend."""

from __future__ import annotations

import os
from typing import Any


def celery_poll_enabled() -> bool:
    return os.environ.get("JOB_POLL_CELERY", "true").lower() in ("true", "1", "yes")


def _task_id(job: dict[str, Any]) -> str | None:
    metadata = job.get("metadata") or {}
    task_id = metadata.get("task_id")
    return str(task_id) if task_id else None


def get_celery_snapshot(task_id: str) -> dict[str, Any] | None:
    """Return Celery AsyncResult state for a task id."""
    try:
        from celery.result import AsyncResult

        from app.tasks import celery_app

        result = AsyncResult(task_id, app=celery_app)
        state = result.state
        ready = result.ready()
        snapshot: dict[str, Any] = {
            "task_id": task_id,
            "state": state,
            "ready": ready,
        }
        if ready:
            snapshot["successful"] = result.successful()
            if result.successful():
                payload = result.result
                snapshot["result"] = payload if isinstance(payload, dict) else {"result": payload}
            elif result.failed():
                snapshot["error"] = str(result.result)
        return snapshot
    except Exception as exc:  # noqa: BLE001 — optional poll path
        return {"task_id": task_id, "state": "UNKNOWN", "ready": False, "error": str(exc)}


def reconcile_job_with_celery(job: dict[str, Any]) -> dict[str, Any]:
    """Poll Celery result backend and sync stale pending/running jobs."""
    if not celery_poll_enabled():
        return job
    if job.get("status") in ("completed", "failed", "cancelled"):
        return job

    task_id = _task_id(job)
    if not task_id:
        return job

    snapshot = get_celery_snapshot(task_id)
    if not snapshot:
        return job

    job = dict(job)
    job["celery"] = {
        "task_id": task_id,
        "state": snapshot.get("state"),
        "ready": snapshot.get("ready", False),
    }

    if not snapshot.get("ready"):
        if snapshot.get("state") in ("STARTED", "RETRY") and job.get("status") == "pending":
            from app.job_store import get_job_store

            refreshed = get_job_store().mark_running(job["job_id"])
            if refreshed:
                job = {**job, **refreshed, "celery": job["celery"]}
        return job

    from app.job_store import get_job_store
    from app.task_jobs import on_task_failure, on_task_success

    store = get_job_store()
    if snapshot.get("successful"):
        payload = snapshot.get("result") or {}
        if isinstance(payload, dict):
            on_task_success(job["job_id"], payload)
    elif snapshot.get("state") == "FAILURE":
        on_task_failure(job["job_id"], Exception(snapshot.get("error") or "celery task failed"))

    refreshed = store.get_job(job["job_id"])
    if refreshed:
        refreshed = dict(refreshed)
        refreshed["celery"] = job["celery"]
        return refreshed
    return job
