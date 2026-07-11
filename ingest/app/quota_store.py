"""Tenant quota enforcement — FR-30."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.catalog_store import get_catalog_store

_DEFAULT_MAX_CHUNKS = 10_000_000
_DEFAULT_MAX_COLLECTIONS = 100


@dataclass(frozen=True)
class QuotaLimits:
    tenant_id: str
    max_chunks: int
    max_collections: int
    query_qps: float
    max_concurrent_streams: int
    max_storage_bytes: int
    max_embed_tokens_day: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "max_chunks": self.max_chunks,
            "max_collections": self.max_collections,
            "query_qps": self.query_qps,
            "max_concurrent_streams": self.max_concurrent_streams,
            "max_storage_bytes": self.max_storage_bytes,
            "max_embed_tokens_day": self.max_embed_tokens_day,
        }


def quota_enforcement_enabled() -> bool:
    return os.environ.get("QUOTA_ENFORCEMENT_ENABLED", "true").lower() in ("true", "1", "yes")


class QuotaStore(ABC):
    @abstractmethod
    def healthcheck(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_quotas(self, tenant_id: str) -> QuotaLimits:
        raise NotImplementedError

    @abstractmethod
    def upsert_quotas(self, tenant_id: str, body: dict[str, Any]) -> QuotaLimits:
        raise NotImplementedError

    @abstractmethod
    def count_collections(self, tenant_id: str) -> int:
        raise NotImplementedError


def _limits_from_row(tenant_id: str, row: dict[str, Any] | None) -> QuotaLimits:
    data = row or {}
    return QuotaLimits(
        tenant_id=tenant_id,
        max_chunks=int(data.get("max_chunks", _DEFAULT_MAX_CHUNKS)),
        max_collections=int(data.get("max_collections", _DEFAULT_MAX_COLLECTIONS)),
        query_qps=float(data.get("query_qps", 2.0)),
        max_concurrent_streams=int(data.get("max_concurrent_streams", 50)),
        max_storage_bytes=int(data.get("max_storage_bytes", 536_870_912_000)),
        max_embed_tokens_day=int(data.get("max_embed_tokens_day", 10_000_000)),
    )


class InMemoryQuotaStore(QuotaStore):
    def __init__(self) -> None:
        self._quotas: dict[str, dict[str, Any]] = {}
        self._collection_counts: dict[str, int] = {}

    def healthcheck(self) -> bool:
        return True

    def get_quotas(self, tenant_id: str) -> QuotaLimits:
        return _limits_from_row(tenant_id, self._quotas.get(tenant_id))

    def upsert_quotas(self, tenant_id: str, body: dict[str, Any]) -> QuotaLimits:
        current = self._quotas.get(tenant_id, {})
        merged = {**current, **body, "tenant_id": tenant_id}
        self._quotas[tenant_id] = merged
        return _limits_from_row(tenant_id, merged)

    def count_collections(self, tenant_id: str) -> int:
        if tenant_id in self._collection_counts:
            return self._collection_counts[tenant_id]
        store = get_catalog_store()
        if hasattr(store, "_documents"):
            return len({key[1] for key in store._documents if key[0] == tenant_id})
        return 0

    def set_collection_count(self, tenant_id: str, count: int) -> None:
        self._collection_counts[tenant_id] = count


class PostgresQuotaStore(QuotaStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn)

    def healthcheck(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True
        except Exception:
            return False

    def _ensure_tenant(self, cur, tenant_id: str) -> None:
        cur.execute(
            """
            INSERT INTO tenants (tenant_id, display_name)
            VALUES (%s, %s)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (tenant_id, tenant_id),
        )

    def get_quotas(self, tenant_id: str) -> QuotaLimits:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT max_chunks, max_collections, query_qps,
                           max_concurrent_streams, max_storage_bytes, max_embed_tokens_day
                    FROM tenant_quotas
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
        if not row:
            return _limits_from_row(tenant_id, None)
        return _limits_from_row(
            tenant_id,
            {
                "max_chunks": row[0],
                "max_collections": row[1],
                "query_qps": float(row[2]),
                "max_concurrent_streams": row[3],
                "max_storage_bytes": row[4],
                "max_embed_tokens_day": row[5],
            },
        )

    def upsert_quotas(self, tenant_id: str, body: dict[str, Any]) -> QuotaLimits:
        limits = self.get_quotas(tenant_id)
        payload = limits.as_dict()
        payload.update(body)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._ensure_tenant(cur, tenant_id)
                cur.execute(
                    """
                    INSERT INTO tenant_quotas (
                        tenant_id, max_chunks, max_collections, query_qps,
                        max_concurrent_streams, max_storage_bytes, max_embed_tokens_day
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        max_chunks = EXCLUDED.max_chunks,
                        max_collections = EXCLUDED.max_collections,
                        query_qps = EXCLUDED.query_qps,
                        max_concurrent_streams = EXCLUDED.max_concurrent_streams,
                        max_storage_bytes = EXCLUDED.max_storage_bytes,
                        max_embed_tokens_day = EXCLUDED.max_embed_tokens_day,
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        int(payload["max_chunks"]),
                        int(payload["max_collections"]),
                        float(payload["query_qps"]),
                        int(payload["max_concurrent_streams"]),
                        int(payload["max_storage_bytes"]),
                        int(payload["max_embed_tokens_day"]),
                    ),
                )
            conn.commit()
        return self.get_quotas(tenant_id)

    def count_collections(self, tenant_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM collections WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
        return int(row[0] if row else 0)


_store: QuotaStore | None = None


def get_quota_store() -> QuotaStore:
    global _store
    if _store is None:
        dsn = os.environ.get("CATALOG_DSN")
        _store = PostgresQuotaStore(dsn) if dsn else InMemoryQuotaStore()
    return _store


def reset_quota_store() -> None:
    global _store
    _store = None


def assert_quota_for_enqueue(
    tenant_id: str,
    *,
    estimated_chunks: int = 1,
    new_collection: bool = False,
) -> QuotaLimits:
    """Raise HTTP 403 when tenant quota would be exceeded."""
    if not quota_enforcement_enabled():
        return _limits_from_row(tenant_id, None)

    store = get_quota_store()
    limits = store.get_quotas(tenant_id)
    current_chunks = get_catalog_store().count_tenant_chunks(tenant_id)
    projected = current_chunks + max(estimated_chunks, 0)

    if projected > limits.max_chunks:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "quota_exceeded",
                "kind": "max_chunks",
                "tenant_id": tenant_id,
                "current_chunks": current_chunks,
                "estimated_chunks": estimated_chunks,
                "max_chunks": limits.max_chunks,
            },
        )

    if new_collection:
        collection_count = store.count_collections(tenant_id)
        if collection_count >= limits.max_collections:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "quota_exceeded",
                    "kind": "max_collections",
                    "tenant_id": tenant_id,
                    "collection_count": collection_count,
                    "max_collections": limits.max_collections,
                },
            )
    return limits
