"""Connector sync HTTP routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.orchestrator import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    mock_result = MagicMock()
    mock_result.id = "task-123"
    monkeypatch.setattr("app.connector_handlers.connector_sync.delay", lambda payload: mock_result)
    with TestClient(app) as test_client:
        yield test_client


def test_collection_sync_enqueue(client: TestClient) -> None:
    response = client.post(
        "/admin/ingest/collection",
        json={
            "tenant_id": "acme",
            "collection_id": "payments-api",
            "version_id": "2026-03-01",
            "mode": "incremental",
            "connector": "s3",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["task_id"] == "task-123"
    assert "job_id" in body
    assert body["stub"] is False
