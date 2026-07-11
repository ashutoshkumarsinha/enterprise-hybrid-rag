"""Ingest backpressure (FR-29) unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.backpressure import assert_enqueue_allowed, check_backpressure
from app.job_store import reset_job_store
from app.orchestrator import app


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATALOG_DSN", raising=False)
    monkeypatch.setenv("INGEST_BACKPRESSURE_ENABLED", "true")
    monkeypatch.setenv("INGEST_BACKPRESSURE_STUB", "true")
    monkeypatch.setenv("INGEST_BACKPRESSURE_STUB_DEPTH", "0")
    monkeypatch.setenv("INGEST_BACKPRESSURE_WARN_DEPTH", "100")
    monkeypatch.setenv("INGEST_BACKPRESSURE_PAUSE_DEPTH", "1000")
    reset_job_store()


def test_check_backpressure_warn_and_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_BACKPRESSURE_STUB_DEPTH", "150")
    status = check_backpressure()
    assert status.warn is True
    assert status.paused is False

    monkeypatch.setenv("INGEST_BACKPRESSURE_STUB_DEPTH", "1200")
    status = check_backpressure()
    assert status.paused is True


def test_assert_enqueue_allowed_raises_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    monkeypatch.setenv("INGEST_BACKPRESSURE_STUB_DEPTH", "2000")
    with pytest.raises(HTTPException) as exc:
        assert_enqueue_allowed()
    assert exc.value.status_code == 503


def test_collection_enqueue_503_when_paused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_BACKPRESSURE_STUB_DEPTH", "5000")
    with TestClient(app) as client:
        response = client.post(
            "/admin/ingest/collection",
            json={"tenant_id": "acme", "collection_id": "docs", "connector": "s3"},
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "backpressure"


def test_collection_enqueue_warn_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_BACKPRESSURE_STUB_DEPTH", "150")
    mock_result = MagicMock()
    mock_result.id = "task-bp"
    monkeypatch.setattr("app.tasks.connector_sync.delay", lambda payload: mock_result)
    with TestClient(app) as client:
        response = client.post(
            "/admin/ingest/collection",
            json={"tenant_id": "acme", "collection_id": "docs", "connector": "s3"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body.get("backpressure_warn") is True
    assert body.get("queue_depth") == 150
