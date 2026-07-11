"""Tenant quota enforcement tests — FR-30."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.catalog_store import InMemoryCatalogStore, reset_catalog_store
from app.job_store import reset_job_store
from app.orchestrator import app
from app.quota_store import InMemoryQuotaStore, assert_quota_for_enqueue, reset_quota_store


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATALOG_DSN", raising=False)
    monkeypatch.setenv("QUOTA_ENFORCEMENT_ENABLED", "true")
    reset_quota_store()
    reset_catalog_store()
    reset_job_store()


def test_quota_blocks_when_chunk_limit_exceeded() -> None:
    store = InMemoryQuotaStore()
    store.upsert_quotas("acme", {"max_chunks": 5})
    catalog = InMemoryCatalogStore()
    catalog.record_from_chunks(
        [
            {
                "uuid": "1",
                "tenant_id": "acme",
                "collection_id": "docs",
                "document_id": "a",
                "version_id": "v1",
                "text": "one",
            }
            for _ in range(4)
        ]
    )

    import app.quota_store as quota_module
    import app.catalog_store as catalog_module

    quota_module._store = store
    catalog_module._store = catalog

    with pytest.raises(HTTPException) as exc:
        assert_quota_for_enqueue("acme", estimated_chunks=2)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "quota_exceeded"


def test_collection_enqueue_403_on_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryQuotaStore()
    store.upsert_quotas("acme", {"max_chunks": 1})
    catalog = InMemoryCatalogStore()
    catalog.record_from_chunks(
        [
            {
                "uuid": "1",
                "tenant_id": "acme",
                "collection_id": "docs",
                "document_id": "a",
                "version_id": "v1",
                "text": "chunk",
            }
        ]
    )
    import app.quota_store as quota_module
    import app.catalog_store as catalog_module

    quota_module._store = store
    catalog_module._store = catalog

    mock_result = MagicMock()
    mock_result.id = "task-quota"
    monkeypatch.setattr("app.tasks.connector_sync.delay", lambda payload: mock_result)

    with TestClient(app) as client:
        response = client.post(
            "/admin/ingest/collection",
            json={"tenant_id": "acme", "collection_id": "docs", "connector": "s3", "chunk_estimate": 1},
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "quota_exceeded"


def test_put_and_get_quotas() -> None:
    with TestClient(app) as client:
        put = client.put("/admin/tenants/acme/quotas", json={"max_chunks": 1000, "max_collections": 3})
        assert put.status_code == 200
        assert put.json()["quotas"]["max_chunks"] == 1000
        get = client.get("/admin/tenants/acme/quotas")
        assert get.status_code == 200
        assert get.json()["quotas"]["max_collections"] == 3
