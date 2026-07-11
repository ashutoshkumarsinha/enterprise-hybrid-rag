"""Ingest job status HTTP routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.job_store import reset_job_store
from app.orchestrator import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("CATALOG_DSN", raising=False)
    reset_job_store()
    with TestClient(app) as test_client:
        yield test_client
    reset_job_store()


def test_get_job_status_after_collection_enqueue(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_result = MagicMock()
    mock_result.id = "task-456"
    monkeypatch.setattr("app.tasks.connector_sync.delay", lambda payload: mock_result)
    created = client.post(
        "/admin/ingest/collection",
        json={
            "tenant_id": "acme",
            "collection_id": "payments-api",
            "mode": "incremental",
            "connector": "s3",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    status = client.get(f"/admin/ingest/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["job_id"] == job_id
    assert body["status"] == "pending"
    assert body["job_type"] == "connector_sync"
    assert body["stub"] is False


def test_get_job_status_not_found(client: TestClient) -> None:
    response = client.get("/admin/ingest/jobs/00000000-0000-4000-8000-000000009999")
    assert response.status_code == 404
