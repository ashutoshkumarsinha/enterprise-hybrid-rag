"""Chunk content-hash dedup before embed (spec §4.6)."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from app.chunk_builder import content_hash


def dedup_key(*, tenant_id: str, content_hash_value: str) -> str:
    return f"dedup:{tenant_id}:{content_hash_value}"


def chunk_content_hash(chunk: dict[str, Any]) -> str:
    value = chunk.get("content_hash")
    if value:
        return str(value)
    return content_hash(str(chunk.get("text", "")))


class DedupStore(ABC):
    @property
    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def lookup_uuids(self, keys: list[str]) -> list[str | None]:
        raise NotImplementedError

    @abstractmethod
    def store_uuids(self, entries: dict[str, str]) -> None:
        raise NotImplementedError


class InMemoryDedupStore(DedupStore):
    def __init__(self) -> None:
        self._entries: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return True

    def lookup_uuids(self, keys: list[str]) -> list[str | None]:
        return [self._entries.get(key) for key in keys]

    def store_uuids(self, entries: dict[str, str]) -> None:
        self._entries.update(entries)

    def purge_tenant(self, tenant_id: str) -> int:
        prefix = f"dedup:{tenant_id}:"
        keys = [key for key in self._entries if key.startswith(prefix)]
        for key in keys:
            del self._entries[key]
        return len(keys)


class RedisDedupStore(DedupStore):
    def __init__(self, url: str, *, mget_batch: int) -> None:
        import redis

        self._client = redis.from_url(url)
        self._mget_batch = mget_batch

    @property
    def enabled(self) -> bool:
        return True

    def lookup_uuids(self, keys: list[str]) -> list[str | None]:
        if not keys:
            return []
        values: list[str | None] = []
        for start in range(0, len(keys), self._mget_batch):
            batch = keys[start : start + self._mget_batch]
            raw = self._client.mget(batch)
            for item in raw:
                if item is None:
                    values.append(None)
                else:
                    values.append(item.decode("utf-8"))
        return values

    def store_uuids(self, entries: dict[str, str]) -> None:
        if not entries:
            return
        pipe = self._client.pipeline()
        for key, uuid in entries.items():
            pipe.set(key, uuid)
        pipe.execute()

    def purge_tenant(self, tenant_id: str) -> int:
        prefix = f"dedup:{tenant_id}:"
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=f"{prefix}*", count=500)
            if keys:
                self._client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        return deleted


class DisabledDedupStore(DedupStore):
    @property
    def enabled(self) -> bool:
        return False

    def lookup_uuids(self, keys: list[str]) -> list[str | None]:
        return [None] * len(keys)

    def store_uuids(self, entries: dict[str, str]) -> None:
        return

    def purge_tenant(self, tenant_id: str) -> int:
        return 0


_store: DedupStore | None = None


def _mget_batch() -> int:
    return int(os.environ.get("DEDUP_MGET_BATCH", os.environ.get("dedup_mget_batch", "100")))


def _dedup_disabled() -> bool:
    return os.environ.get("DEDUP_ENABLED", "true").lower() in ("false", "0", "no")


def get_dedup_store() -> DedupStore:
    global _store
    if _store is None:
        if _dedup_disabled():
            _store = DisabledDedupStore()
        else:
            url = os.environ.get("REDIS_DEDUP_URL") or os.environ.get("REDIS_URL")
            _store = RedisDedupStore(url, mget_batch=_mget_batch()) if url else InMemoryDedupStore()
    return _store


def reset_dedup_store() -> None:
    global _store
    _store = None


def partition_deduped_chunks(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Return chunks that still need embed/upsert and a dedup skip count."""
    store = get_dedup_store()
    if not store.enabled or not chunks:
        return chunks, 0

    keys = [
        dedup_key(tenant_id=chunk["tenant_id"], content_hash_value=chunk_content_hash(chunk))
        for chunk in chunks
    ]
    existing = store.lookup_uuids(keys)
    to_write: list[dict[str, Any]] = []
    skipped = 0
    for chunk, key, uuid in zip(chunks, keys, existing, strict=True):
        if uuid:
            skipped += 1
            continue
        to_write.append(chunk)
    return to_write, skipped


def record_written_chunks(chunks: list[dict[str, Any]]) -> None:
    store = get_dedup_store()
    if not store.enabled or not chunks:
        return
    entries = {
        dedup_key(tenant_id=chunk["tenant_id"], content_hash_value=chunk_content_hash(chunk)): str(
            chunk["uuid"]
        )
        for chunk in chunks
    }
    store.store_uuids(entries)


def purge_tenant_dedup_keys(tenant_id: str) -> int:
    store = get_dedup_store()
    if not store.enabled:
        return 0
    return store.purge_tenant(tenant_id)
