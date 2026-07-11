"""Tenant offboarding purge — E-21."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.catalog_store import InMemoryCatalogStore, reset_catalog_store
from app.dedup_store import InMemoryDedupStore, dedup_key, reset_dedup_store
from app.orchestrator import app
from app.tenant_purge import PurgeConfirmationRequired, purge_tenant


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_catalog_store()
    reset_dedup_store()


def _seed_tenant(store: InMemoryCatalogStore, tenant_id: str = "acme") -> None:
    chunks = [
        {
            "uuid": "00000000-0000-4000-8000-000000000001",
            "tenant_id": tenant_id,
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": "v1",
            "title": "Guide",
            "text": "body",
            "content_hash": "hash-1",
            "ingested_at": datetime.now(UTC).isoformat(),
        },
        {
            "uuid": "00000000-0000-4000-8000-000000000002",
            "tenant_id": tenant_id,
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": "v1",
            "title": "Guide",
            "text": "more",
            "content_hash": "hash-2",
            "ingested_at": datetime.now(UTC).isoformat(),
        },
    ]
    store.record_from_chunks(chunks, job_id="job-1")


def test_tenant_scope_counts_documents_and_chunks() -> None:
    store = InMemoryCatalogStore()
    _seed_tenant(store)
    scope = store.tenant_scope("acme")
    assert scope["documents"] == 1
    assert scope["document_versions"] == 1
    assert scope["chunks"] == 2


def test_purge_tenant_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryCatalogStore()
    _seed_tenant(store)
    monkeypatch.setattr("app.tenant_purge.get_catalog_store", lambda: store)

    result = purge_tenant("acme", dry_run=True)
    assert result["dry_run"] is True
    assert result["scope"]["chunks"] == 2
    assert store.tenant_scope("acme")["documents"] == 1


def test_purge_tenant_requires_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryCatalogStore()
    _seed_tenant(store)
    monkeypatch.setattr("app.tenant_purge.get_catalog_store", lambda: store)

    with pytest.raises(PurgeConfirmationRequired):
        purge_tenant("acme", confirm=False)


def test_purge_tenant_deletes_all_planes(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryCatalogStore()
    _seed_tenant(store)
    dedup = InMemoryDedupStore()
    dedup.store_uuids({dedup_key(tenant_id="acme", content_hash_value="hash-1"): "uuid-1"})
    events: list[dict] = []

    monkeypatch.setattr("app.tenant_purge.get_catalog_store", lambda: store)
    monkeypatch.setattr("app.tenant_purge.purge_tenant_dedup_keys", lambda tenant_id: dedup.purge_tenant(tenant_id))
    monkeypatch.setattr("app.tenant_purge.publish_tenant_purged", lambda **kwargs: events.append(kwargs))
    monkeypatch.setenv("QDRANT_STUB", "true")
    monkeypatch.setenv("NEO4J_STUB", "true")
    monkeypatch.setenv("MINIO_STUB", "true")

    result = purge_tenant("acme", confirm=True)
    assert result["purged"] is True
    assert result["qdrant_points"] == 2
    assert result["catalog"]["documents"] == 1
    assert result["dedup_keys"] == 1
    assert store.tenant_scope("acme")["chunks"] == 0
    assert events == [{"tenant_id": "acme"}]


def test_admin_purge_tenant_route() -> None:
    with TestClient(app) as client:
        dry = client.post("/admin/tenants/acme/purge", json={"dry_run": True})
        assert dry.status_code == 200
        assert dry.json()["dry_run"] is True

        blocked = client.post("/admin/tenants/acme/purge", json={})
        assert blocked.status_code == 422
        assert blocked.json()["detail"]["code"] == "confirmation_required"

        confirmed = client.post(
            "/admin/tenants/acme/purge",
            json={"confirm": True},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["purged"] is True


def test_publish_tenant_purged_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    from app.events import publish_tenant_purged

    publish_tenant_purged(tenant_id="acme")
