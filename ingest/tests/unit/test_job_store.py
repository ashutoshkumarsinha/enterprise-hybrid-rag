"""Ingest job store unit tests."""

from __future__ import annotations

import pytest

from app.job_store import InMemoryJobStore, reset_job_store


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATALOG_DSN", raising=False)
    reset_job_store()


def test_job_lifecycle() -> None:
    store = InMemoryJobStore()
    job = store.create_job(
        tenant_id="acme",
        collection_id="docs",
        mode="incremental",
        job_type="connector_sync",
    )
    assert job["status"] == "pending"
    running = store.mark_running(job["job_id"])
    assert running is not None
    assert running["status"] == "running"
    done = store.mark_completed(
        job["job_id"],
        chunk_count=12,
        files_done=3,
        files_total=3,
    )
    assert done is not None
    assert done["status"] == "completed"
    assert done["chunk_count"] == 12


def test_job_failed() -> None:
    store = InMemoryJobStore()
    job = store.create_job(tenant_id="acme", collection_id="docs")
    failed = store.mark_failed(job["job_id"], error_message="parse error")
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["error_message"] == "parse error"
