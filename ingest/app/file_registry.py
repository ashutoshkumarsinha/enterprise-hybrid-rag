"""Incremental file registry for connector sync."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class FileRegistry(ABC):
    @abstractmethod
    def should_ingest(self, *, registry_key: str, etag: str | None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_ingested(self, *, registry_key: str, etag: str | None) -> None:
        raise NotImplementedError


class InMemoryFileRegistry(FileRegistry):
    def __init__(self) -> None:
        self._entries: dict[str, str | None] = {}

    def should_ingest(self, *, registry_key: str, etag: str | None) -> bool:
        return self._entries.get(registry_key) != etag

    def mark_ingested(self, *, registry_key: str, etag: str | None) -> None:
        self._entries[registry_key] = etag


class RedisFileRegistry(FileRegistry):
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.from_url(url)

    def should_ingest(self, *, registry_key: str, etag: str | None) -> bool:
        stored = self._client.get(registry_key)
        if stored is None:
            return True
        return stored.decode("utf-8") != (etag or "")

    def mark_ingested(self, *, registry_key: str, etag: str | None) -> None:
        self._client.set(registry_key, etag or "")


_registry: FileRegistry | None = None


def registry_key(*, tenant_id: str, collection_id: str, object_key: str) -> str:
    return f"file:{tenant_id}:{collection_id}:{object_key}"


def get_file_registry() -> FileRegistry:
    global _registry
    if _registry is None:
        url = os.environ.get("REDIS_URL")
        _registry = RedisFileRegistry(url) if url else InMemoryFileRegistry()
    return _registry


def reset_file_registry() -> None:
    global _registry
    _registry = None
