"""Celery task job lifecycle helpers."""

from __future__ import annotations

from typing import Any

from app.job_store import get_job_store


def _store():
    return get_job_store()


def on_task_start(job_id: str | None) -> None:
    if job_id:
        _store().mark_running(job_id)


def on_task_success(job_id: str | None, result: dict[str, Any]) -> None:
    if not job_id:
        return
    errors = result.get("errors") or []
    error_count = int(result.get("error_count", len(errors)))
    status_errors = errors if isinstance(errors, list) else []
    error_message = None
    if status_errors:
        error_message = "; ".join(
            f"{item.get('key', 'task')}: {item.get('message', 'error')}" for item in status_errors[:5]
        )
    elif result.get("error_message"):
        error_message = str(result["error_message"])

    _store().mark_completed(
        job_id,
        chunk_count=int(result.get("chunk_count", result.get("validated", result.get("written", 0)))),
        files_done=int(result.get("ingested", result.get("files_done", 1 if result.get("written") else 0))),
        files_total=int(result.get("files_total", result.get("ingested", 0))),
        error_count=error_count,
        error_message=error_message,
    )


def on_task_failure(job_id: str | None, exc: BaseException) -> None:
    if job_id:
        _store().mark_failed(job_id, error_message=str(exc))
