"""Celery result backend job polling."""

from __future__ import annotations

import pytest

from app.celery_results import celery_poll_enabled, reconcile_job_with_celery
from app.job_store import InMemoryJobStore, get_job_store, reset_job_store


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATALOG_DSN", raising=False)
    monkeypatch.setenv("JOB_POLL_CELERY", "true")
    reset_job_store()


def test_attach_task_id() -> None:
    store = InMemoryJobStore()
    job = store.create_job(tenant_id="acme", collection_id="docs", job_type="document")
    updated = store.attach_task_id(job["job_id"], "celery-task-1")
    assert updated is not None
    assert updated["metadata"]["task_id"] == "celery-task-1"


def test_reconcile_marks_completed_from_celery(monkeypatch: pytest.MonkeyPatch) -> None:
    store = get_job_store()
    job = store.create_job(tenant_id="acme", collection_id="docs", job_type="connector_sync")
    store.attach_task_id(job["job_id"], "celery-task-2")

    monkeypatch.setattr(
        "app.celery_results.get_celery_snapshot",
        lambda task_id: {
            "task_id": task_id,
            "state": "SUCCESS",
            "ready": True,
            "successful": True,
            "result": {"validated": 5, "written": 5, "chunk_count": 5},
        },
    )

    reconciled = reconcile_job_with_celery(store.get_job(job["job_id"]) or {})
    assert reconciled["status"] == "completed"
    assert reconciled["chunk_count"] == 5
    assert reconciled["celery"]["state"] == "SUCCESS"


def test_reconcile_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOB_POLL_CELERY", "false")
    store = InMemoryJobStore()
    job = store.create_job(tenant_id="acme", collection_id="docs")
    store.attach_task_id(job["job_id"], "celery-task-3")
    reconciled = reconcile_job_with_celery(store.get_job(job["job_id"]) or {})
    assert reconciled["status"] == "pending"
    assert "celery" not in reconciled
