"""Document version retention prune — E-22."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.catalog_store import InMemoryCatalogStore, reset_catalog_store
from app.version_prune import prune_versions


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_catalog_store()


def _record_version(
    store: InMemoryCatalogStore,
    *,
    version_id: str,
    ingested_at: str,
    chunk_count: int = 1,
) -> None:
    chunks = [
        {
            "uuid": f"00000000-0000-4000-8000-{version_id:0>12}",
            "tenant_id": "acme",
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": version_id,
            "title": "Guide",
            "text": f"body-{version_id}",
            "content_hash": f"hash-{version_id}",
            "ingested_at": ingested_at,
        }
        for _ in range(chunk_count)
    ]
    store.record_from_chunks(chunks, job_id=f"job-{version_id}")


def test_list_prunable_versions_keeps_latest_and_last_n() -> None:
    store = InMemoryCatalogStore()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index, version_id in enumerate(["v1", "v2", "v3", "v4", "v5"], start=1):
        _record_version(
            store,
            version_id=version_id,
            ingested_at=(base + timedelta(days=index)).isoformat(),
        )
    store._documents[("acme", "docs", "guide")]["latest_version_id"] = "v5"

    prunable = store.list_prunable_versions(keep_count=3)
    version_ids = {row["version_id"] for row in prunable}
    assert version_ids == {"v1", "v2"}
    assert "v5" not in version_ids
    assert "v4" not in version_ids


def test_prune_versions_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryCatalogStore()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index, version_id in enumerate(["v1", "v2", "v3", "v4"], start=1):
        _record_version(
            store,
            version_id=version_id,
            ingested_at=(base + timedelta(days=index)).isoformat(),
            chunk_count=2,
        )
    store._documents[("acme", "docs", "guide")]["latest_version_id"] = "v4"
    monkeypatch.setattr("app.version_prune.get_catalog_store", lambda: store)

    result = prune_versions(keep_count=2, dry_run=True)
    assert result["dry_run"] is True
    assert result["candidates"] == 2
    assert len(store._versions) == 4


def test_prune_versions_deletes_catalog_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryCatalogStore()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index, version_id in enumerate(["v1", "v2", "v3", "v4"], start=1):
        _record_version(
            store,
            version_id=version_id,
            ingested_at=(base + timedelta(days=index)).isoformat(),
            chunk_count=3,
        )
    store._documents[("acme", "docs", "guide")]["latest_version_id"] = "v4"
    monkeypatch.setattr("app.version_prune.get_catalog_store", lambda: store)
    monkeypatch.setenv("QDRANT_STUB", "true")
    monkeypatch.setenv("NEO4J_STUB", "true")

    result = prune_versions(keep_count=2)
    assert result["pruned"] == 2
    assert result["catalog_rows"] == 2
    assert result["qdrant_points"] == 6
    assert ("acme", "docs", "guide", "v1") not in store._versions
    assert ("acme", "docs", "guide", "v4") in store._versions


def test_admin_prune_versions_route() -> None:
    from fastapi.testclient import TestClient

    from app.orchestrator import app

    with TestClient(app) as test_client:
        response = test_client.post("/admin/versions/prune", json={"dry_run": True, "keep_count": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["keep_count"] == 3
