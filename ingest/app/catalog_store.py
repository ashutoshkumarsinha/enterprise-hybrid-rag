"""Catalog document registry — upsert documents + document_versions on ingest."""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any


class CatalogStore(ABC):
    @abstractmethod
    def healthcheck(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def record_from_chunks(
        self,
        chunks: list[dict[str, Any]],
        *,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


def _version_content_hash(chunks: list[dict[str, Any]]) -> str:
    parts = sorted(chunk.get("content_hash") or hashlib.sha256(chunk["text"].encode()).hexdigest() for chunk in chunks)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _group_chunks(chunks: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        tenant_id = chunk.get("tenant_id")
        collection_id = chunk.get("collection_id")
        document_id = chunk.get("document_id")
        version_id = chunk.get("version_id") or "v1"
        if tenant_id and collection_id and document_id:
            groups[(tenant_id, collection_id, document_id, version_id)].append(chunk)
    return groups


class InMemoryCatalogStore(CatalogStore):
    def __init__(self) -> None:
        self._documents: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._versions: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def healthcheck(self) -> bool:
        return True

    def record_from_chunks(
        self,
        chunks: list[dict[str, Any]],
        *,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        recorded = 0
        now = datetime.now(UTC).isoformat()
        for key, doc_chunks in _group_chunks(chunks).items():
            tenant_id, collection_id, document_id, version_id = key
            first = doc_chunks[0]
            doc_key = (tenant_id, collection_id, document_id)
            self._documents[doc_key] = {
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "document_id": document_id,
                "title": first.get("title") or document_id,
                "source_uri": first.get("source_uri"),
                "source_system": first.get("source_system"),
                "latest_version_id": version_id,
                "updated_at": now,
            }
            ver_key = (*doc_key, version_id)
            self._versions[ver_key] = {
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "document_id": document_id,
                "version_id": version_id,
                "content_hash": _version_content_hash(doc_chunks),
                "chunk_count": len(doc_chunks),
                "ingest_job_id": job_id,
                "ingested_at": first.get("ingested_at") or now,
            }
            recorded += 1
        return {"documents_recorded": recorded}


class PostgresCatalogStore(CatalogStore):
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

    def _ensure_scope(self, cur, *, tenant_id: str, collection_id: str) -> None:
        cur.execute(
            """
            INSERT INTO tenants (tenant_id, display_name)
            VALUES (%s, %s)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (tenant_id, tenant_id),
        )
        cur.execute(
            """
            INSERT INTO collections (tenant_id, collection_id, display_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (tenant_id, collection_id) DO NOTHING
            """,
            (tenant_id, collection_id, collection_id),
        )

    def record_from_chunks(
        self,
        chunks: list[dict[str, Any]],
        *,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        recorded = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for key, doc_chunks in _group_chunks(chunks).items():
                    tenant_id, collection_id, document_id, version_id = key
                    first = doc_chunks[0]
                    self._ensure_scope(cur, tenant_id=tenant_id, collection_id=collection_id)
                    cur.execute(
                        """
                        INSERT INTO documents (
                            tenant_id, collection_id, document_id, title,
                            source_uri, source_system, latest_version_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tenant_id, collection_id, document_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            source_uri = COALESCE(EXCLUDED.source_uri, documents.source_uri),
                            source_system = COALESCE(EXCLUDED.source_system, documents.source_system),
                            latest_version_id = EXCLUDED.latest_version_id,
                            updated_at = now()
                        """,
                        (
                            tenant_id,
                            collection_id,
                            document_id,
                            first.get("title") or document_id,
                            first.get("source_uri"),
                            first.get("source_system"),
                            version_id,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO document_versions (
                            tenant_id, collection_id, document_id, version_id,
                            content_hash, chunk_count, ingest_job_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tenant_id, collection_id, document_id, version_id) DO UPDATE SET
                            content_hash = EXCLUDED.content_hash,
                            chunk_count = EXCLUDED.chunk_count,
                            ingest_job_id = COALESCE(EXCLUDED.ingest_job_id, document_versions.ingest_job_id),
                            ingested_at = now()
                        """,
                        (
                            tenant_id,
                            collection_id,
                            document_id,
                            version_id,
                            _version_content_hash(doc_chunks),
                            len(doc_chunks),
                            job_id,
                        ),
                    )
                    recorded += 1
            conn.commit()
        return {"documents_recorded": recorded}


_store: CatalogStore | None = None


def get_catalog_store() -> CatalogStore:
    global _store
    if _store is None:
        dsn = os.environ.get("CATALOG_DSN")
        _store = PostgresCatalogStore(dsn) if dsn else InMemoryCatalogStore()
    return _store


def reset_catalog_store() -> None:
    global _store
    _store = None
