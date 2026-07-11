"""Chunk dedup store unit tests."""

from __future__ import annotations

import pytest

from app.chunk_builder import content_hash
from app.dedup_store import (
    InMemoryDedupStore,
    dedup_key,
    partition_deduped_chunks,
    record_written_chunks,
    reset_dedup_store,
)


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_DEDUP_URL", raising=False)
    monkeypatch.setenv("DEDUP_ENABLED", "true")
    reset_dedup_store()


def _chunk(text: str, *, uuid: str) -> dict:
    return {
        "uuid": uuid,
        "tenant_id": "acme",
        "collection_id": "docs",
        "document_id": "guide",
        "version_id": "v1",
        "title": "Guide",
        "text": text,
        "type": "text",
        "ingested_at": "2026-01-01T00:00:00+00:00",
        "content_hash": content_hash(text),
    }


def test_partition_skips_known_hash() -> None:
    chunk = _chunk("Rotate API keys monthly.", uuid="00000000-0000-4000-8000-000000000001")
    record_written_chunks([chunk])
    to_write, skipped = partition_deduped_chunks([chunk])
    assert to_write == []
    assert skipped == 1


def test_partition_allows_new_hash() -> None:
    chunk = _chunk("Enable MFA for admins.", uuid="00000000-0000-4000-8000-000000000002")
    to_write, skipped = partition_deduped_chunks([chunk])
    assert len(to_write) == 1
    assert skipped == 0


def test_dedup_key_format() -> None:
    key = dedup_key(tenant_id="acme", content_hash_value="abc123")
    assert key == "dedup:acme:abc123"


def test_in_memory_mget_batch() -> None:
    store = InMemoryDedupStore()
    keys = [
        dedup_key(tenant_id="acme", content_hash_value="one"),
        dedup_key(tenant_id="acme", content_hash_value="two"),
    ]
    store.store_uuids({keys[0]: "uuid-1"})
    assert store.lookup_uuids(keys) == ["uuid-1", None]
