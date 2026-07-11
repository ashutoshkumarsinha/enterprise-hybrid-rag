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

    @abstractmethod
    def count_tenant_chunks(self, tenant_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_prunable_versions(self, *, keep_count: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete_versions(self, versions: list[dict[str, Any]]) -> int:
        raise NotImplementedError

    @abstractmethod
    def tenant_scope(self, tenant_id: str) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def purge_tenant(self, tenant_id: str) -> dict[str, int]:
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

    def count_tenant_chunks(self, tenant_id: str) -> int:
        return sum(
            int(version.get("chunk_count", 0))
            for key, version in self._versions.items()
            if key[0] == tenant_id
        )

    def list_prunable_versions(self, *, keep_count: int) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for (tenant_id, collection_id, document_id, version_id), version in self._versions.items():
            doc = self._documents.get((tenant_id, collection_id, document_id))
            if not doc:
                continue
            grouped[(tenant_id, collection_id, document_id)].append(
                {
                    **version,
                    "latest_version_id": doc.get("latest_version_id"),
                }
            )

        prunable: list[dict[str, Any]] = []
        for versions in grouped.values():
            versions.sort(
                key=lambda row: (row.get("ingested_at", ""), row["version_id"]),
                reverse=True,
            )
            latest_version_id = versions[0].get("latest_version_id") if versions else None
            for version in versions[keep_count:]:
                if version["version_id"] == latest_version_id:
                    continue
                prunable.append(
                    {
                        "tenant_id": version["tenant_id"],
                        "collection_id": version["collection_id"],
                        "document_id": version["document_id"],
                        "version_id": version["version_id"],
                        "chunk_count": int(version.get("chunk_count", 0)),
                    }
                )
        return prunable

    def delete_versions(self, versions: list[dict[str, Any]]) -> int:
        deleted = 0
        for version in versions:
            key = (
                version["tenant_id"],
                version["collection_id"],
                version["document_id"],
                version["version_id"],
            )
            if key in self._versions:
                del self._versions[key]
                deleted += 1
        return deleted

    def tenant_scope(self, tenant_id: str) -> dict[str, int]:
        documents = sum(1 for key in self._documents if key[0] == tenant_id)
        versions = sum(1 for key in self._versions if key[0] == tenant_id)
        collections = len({key[1] for key in self._documents if key[0] == tenant_id})
        chunks = self.count_tenant_chunks(tenant_id)
        return {
            "collections": collections,
            "documents": documents,
            "document_versions": versions,
            "chunks": chunks,
        }

    def purge_tenant(self, tenant_id: str) -> dict[str, int]:
        scope = self.tenant_scope(tenant_id)
        self._versions = {key: value for key, value in self._versions.items() if key[0] != tenant_id}
        self._documents = {key: value for key, value in self._documents.items() if key[0] != tenant_id}
        return scope


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

    def count_tenant_chunks(self, tenant_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(chunk_count), 0)
                    FROM document_versions
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
        return int(row[0] if row else 0)

    def list_prunable_versions(self, *, keep_count: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH ranked AS (
                        SELECT
                            dv.tenant_id,
                            dv.collection_id,
                            dv.document_id,
                            dv.version_id,
                            dv.chunk_count,
                            d.latest_version_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY dv.tenant_id, dv.collection_id, dv.document_id
                                ORDER BY dv.ingested_at DESC, dv.version_id DESC
                            ) AS rn
                        FROM document_versions dv
                        JOIN documents d
                          ON d.tenant_id = dv.tenant_id
                         AND d.collection_id = dv.collection_id
                         AND d.document_id = dv.document_id
                        WHERE NOT d.tombstoned
                    )
                    SELECT tenant_id, collection_id, document_id, version_id, chunk_count
                    FROM ranked
                    WHERE rn > %s
                      AND version_id <> latest_version_id
                    ORDER BY tenant_id, collection_id, document_id, version_id
                    """,
                    (keep_count,),
                )
                rows = cur.fetchall()
        return [
            {
                "tenant_id": row[0],
                "collection_id": row[1],
                "document_id": row[2],
                "version_id": row[3],
                "chunk_count": int(row[4]),
            }
            for row in rows
        ]

    def delete_versions(self, versions: list[dict[str, Any]]) -> int:
        if not versions:
            return 0
        deleted = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for version in versions:
                    cur.execute(
                        """
                        DELETE FROM document_versions
                        WHERE tenant_id = %s
                          AND collection_id = %s
                          AND document_id = %s
                          AND version_id = %s
                        """,
                        (
                            version["tenant_id"],
                            version["collection_id"],
                            version["document_id"],
                            version["version_id"],
                        ),
                    )
                    deleted += cur.rowcount
            conn.commit()
        return deleted

    def tenant_scope(self, tenant_id: str) -> dict[str, int]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM collections WHERE tenant_id = %s",
                    (tenant_id,),
                )
                collections = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT COUNT(*) FROM documents WHERE tenant_id = %s",
                    (tenant_id,),
                )
                documents = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT COUNT(*) FROM document_versions WHERE tenant_id = %s",
                    (tenant_id,),
                )
                versions = int(cur.fetchone()[0])
        return {
            "collections": collections,
            "documents": documents,
            "document_versions": versions,
            "chunks": self.count_tenant_chunks(tenant_id),
        }

    def purge_tenant(self, tenant_id: str) -> dict[str, int]:
        scope = self.tenant_scope(tenant_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ingest_jobs WHERE tenant_id = %s", (tenant_id,))
                jobs_deleted = cur.rowcount
                cur.execute("DELETE FROM tenants WHERE tenant_id = %s", (tenant_id,))
                tenant_deleted = cur.rowcount
            conn.commit()
        scope["ingest_jobs"] = jobs_deleted
        scope["tenants"] = tenant_deleted
        return scope


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
