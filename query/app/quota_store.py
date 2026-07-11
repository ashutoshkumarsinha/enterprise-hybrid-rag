"""Read-only tenant quota limits for query admission — FR-30."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.settings import Settings, get_settings


@dataclass(frozen=True)
class TenantQuotaLimits:
    tenant_id: str
    query_qps: float
    max_concurrent_streams: int

    @property
    def queries_per_minute(self) -> int:
        return max(int(self.query_qps * 60), 1)


def _default_limits(tenant_id: str) -> TenantQuotaLimits:
    qpm = int(os.environ.get("TENANT_QUERIES_PER_MINUTE", "120"))
    return TenantQuotaLimits(
        tenant_id=tenant_id,
        query_qps=qpm / 60.0,
        max_concurrent_streams=int(os.environ.get("MAX_CONCURRENT_STREAMS_PER_TENANT", "50")),
    )


class QuotaStore(ABC):
    @abstractmethod
    def get_limits(self, tenant_id: str) -> TenantQuotaLimits:
        raise NotImplementedError

    def get_qdrant_collection_suffix(self, tenant_id: str) -> str | None:
        return None


class InMemoryQuotaStore(QuotaStore):
    def __init__(self) -> None:
        self._limits: dict[str, TenantQuotaLimits] = {}
        self._suffixes: dict[str, str] = {}

    def set_qdrant_suffix(self, tenant_id: str, suffix: str) -> None:
        self._suffixes[tenant_id] = suffix

    def get_qdrant_collection_suffix(self, tenant_id: str) -> str | None:
        return self._suffixes.get(tenant_id)

    def set_limits(self, tenant_id: str, *, query_qps: float, max_concurrent_streams: int) -> None:
        self._limits[tenant_id] = TenantQuotaLimits(
            tenant_id=tenant_id,
            query_qps=query_qps,
            max_concurrent_streams=max_concurrent_streams,
        )

    def get_limits(self, tenant_id: str) -> TenantQuotaLimits:
        return self._limits.get(tenant_id, _default_limits(tenant_id))


class PostgresQuotaStore(QuotaStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn)

    def get_limits(self, tenant_id: str) -> TenantQuotaLimits:
        defaults = _default_limits(tenant_id)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT query_qps, max_concurrent_streams
                        FROM tenant_quotas
                        WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                    row = cur.fetchone()
        except Exception:
            return defaults
        if not row:
            return defaults
        return TenantQuotaLimits(
            tenant_id=tenant_id,
            query_qps=float(row[0]),
            max_concurrent_streams=int(row[1]),
        )

    def get_qdrant_collection_suffix(self, tenant_id: str) -> str | None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT qdrant_collection_suffix
                        FROM tenant_quotas
                        WHERE tenant_id = %s
                        """,
                        (tenant_id,),
                    )
                    row = cur.fetchone()
        except Exception:
            return None
        if not row or not row[0]:
            return None
        return str(row[0]).strip()


_store: QuotaStore | None = None


def get_quota_store(settings: Settings | None = None) -> QuotaStore:
    global _store
    if _store is None:
        settings = settings or get_settings()
        dsn = settings.catalog_dsn_ro
        _store = PostgresQuotaStore(dsn) if dsn else InMemoryQuotaStore()
    return _store


def reset_quota_store() -> None:
    global _store
    _store = None
