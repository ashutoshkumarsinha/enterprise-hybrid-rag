"""Scheduled connector sync Celery task."""

from __future__ import annotations

import json

import pytest

from app.job_store import reset_job_store
from app.tasks import scheduled_connector_sync


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATALOG_DSN", raising=False)
    reset_job_store()


def test_scheduled_sync_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNECTOR_BEAT_ENABLED", "false")
    result = scheduled_connector_sync()
    assert result["skipped"] is True
    assert result["enqueued"] == 0


def test_scheduled_sync_enqueues_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNECTOR_BEAT_ENABLED", "true")
    monkeypatch.setenv(
        "CONNECTOR_BEAT_TARGETS",
        json.dumps(
            [
                {"tenant_id": "acme", "collection_id": "payments-api", "connector": "s3"},
                {"tenant_id": "acme", "collection_id": "internal-only", "connector": "filesystem"},
            ]
        ),
    )
    calls: list[dict] = []

    def _fake_delay(payload: dict) -> object:
        calls.append(payload)
        class Result:
            id = f"task-{len(calls)}"

        return Result()

    monkeypatch.setattr("app.tasks.connector_sync.delay", _fake_delay)
    result = scheduled_connector_sync()
    assert result["enqueued"] == 2
    assert len(calls) == 2
    assert all(call.get("job_id") for call in calls)
