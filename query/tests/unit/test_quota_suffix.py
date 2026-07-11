"""Query quota suffix resolution for regulated Qdrant collections."""

from __future__ import annotations

from app.quota_store import InMemoryQuotaStore, reset_quota_store


def test_query_quota_store_returns_qdrant_suffix() -> None:
    reset_quota_store()
    store = InMemoryQuotaStore()
    store.set_qdrant_suffix("acme", "acme")
    assert store.get_qdrant_collection_suffix("acme") == "acme"
