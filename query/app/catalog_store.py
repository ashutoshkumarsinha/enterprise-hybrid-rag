"""Postgres catalog reads for MCP catalog tools.

Spec: §4.4.1 · §7.3 · §9.4.2 ACL · FR-03.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.acl import can_read_document, principals_for_acl
from app.acl_cache import get_acl_entry, set_acl_entry
from app.models import AuthContext
from app.settings import Settings, get_settings

DocumentRow = dict[str, Any]


class CatalogStore(ABC):
    @abstractmethod
    def healthcheck(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_indexed_documents(
        self,
        *,
        tenant_id: str,
        principal: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[DocumentRow], str | None]:
        raise NotImplementedError

    @abstractmethod
    def get_document_metadata(
        self,
        *,
        tenant_id: str,
        principal: str,
        document_id: str,
        collection_id: str | None = None,
        version_id: str | None = None,
    ) -> DocumentRow | None:
        raise NotImplementedError


def format_documents_markdown(documents: list[DocumentRow]) -> str:
    """Render catalog rows as a markdown table (§7.3)."""
    if not documents:
        return "_No indexed documents found for your access scope._"
    lines = [
        "| document_id | title | version | chunks | ingested_at |",
        "| --- | --- | --- | --- | --- |",
    ]
    for doc in documents:
        lines.append(
            "| {document_id} | {title} | {version} | {chunk_count} | {ingested_at} |".format(
                document_id=doc.get("document_id", ""),
                title=(doc.get("title") or "").replace("|", "\\|"),
                version=doc.get("version_id") or doc.get("latest_version_id") or "—",
                chunk_count=doc.get("chunk_count", 0),
                ingested_at=doc.get("ingested_at") or "—",
            )
        )
    return "\n".join(lines)


class InMemoryCatalogStore(CatalogStore):
    """Dev/test catalog when ``CATALOG_DSN_RO`` is unset."""

    def __init__(self) -> None:
        self._collections: dict[tuple[str, str], dict[str, Any]] = {
            ("acme", "payments-api"): {"default_acl": [], "display_name": "Payments API"},
            ("acme", "internal-only"): {
                "default_acl": ["user:alice"],
                "display_name": "Internal",
            },
        }
        self._documents: list[DocumentRow] = [
            {
                "tenant_id": "acme",
                "collection_id": "payments-api",
                "document_id": "admin-guide",
                "title": "Admin Guide",
                "latest_version_id": "2026-03-01",
                "version_id": "2026-03-01",
                "chunk_count": 42,
                "ingested_at": "2026-03-01T12:00:00+00:00",
                "source_uri": "s3://docs/admin-guide.pdf",
                "source_system": "s3",
                "tags": ["api", "security"],
            },
            {
                "tenant_id": "acme",
                "collection_id": "payments-api",
                "document_id": "refund-policy",
                "title": "Refund Policy",
                "latest_version_id": "2026-02-15",
                "version_id": "2026-02-15",
                "chunk_count": 18,
                "ingested_at": "2026-02-15T09:30:00+00:00",
                "source_uri": "s3://docs/refund-policy.md",
                "source_system": "s3",
                "tags": ["policy"],
            },
            {
                "tenant_id": "acme",
                "collection_id": "internal-only",
                "document_id": "payroll",
                "title": "Payroll Runbook",
                "latest_version_id": "v1",
                "version_id": "v1",
                "chunk_count": 7,
                "ingested_at": "2026-01-10T08:00:00+00:00",
                "source_uri": None,
                "source_system": "filesystem",
                "tags": [],
            },
        ]
        self._grants: list[dict[str, Any]] = [
            {
                "tenant_id": "acme",
                "principal": "user:alice",
                "collection_id": "internal-only",
                "document_id": None,
                "permission": "read",
            }
        ]

    def healthcheck(self) -> bool:
        return True

    def _acl_context(self, tenant_id: str, principal: str) -> tuple[set[str], dict[tuple[str, str], list[Any]], list[dict[str, Any]]]:
        principals = principals_for_acl(
            AuthContext(tenant_id=tenant_id, principal=principal, permissions=[], auth_method="mcp_token")
        )
        default_acls = {
            key: list(value.get("default_acl") or [])
            for key, value in self._collections.items()
            if key[0] == tenant_id
        }
        grants = [g for g in self._grants if g["tenant_id"] == tenant_id]
        return principals, default_acls, grants

    def _allowed(
        self,
        doc: DocumentRow,
        principals: set[str],
        default_acls: dict[tuple[str, str], list[Any]],
        grants: list[dict[str, Any]],
    ) -> bool:
        key = (doc["tenant_id"], doc["collection_id"])
        default_acl = default_acls.get(key, [])
        return can_read_document(
            principals,
            collection_id=doc["collection_id"],
            document_id=doc["document_id"],
            default_acl=default_acl,
            grants=grants,
        )

    def list_indexed_documents(
        self,
        *,
        tenant_id: str,
        principal: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[DocumentRow], str | None]:
        principals, default_acls, grants = self._acl_context(tenant_id, principal)
        rows = [
            doc
            for doc in self._documents
            if doc["tenant_id"] == tenant_id
            and (collection_id is None or doc["collection_id"] == collection_id)
            and (document_id is None or doc["document_id"] == document_id)
            and self._allowed(doc, principals, default_acls, grants)
        ]
        rows.sort(key=lambda d: (d["collection_id"], d["document_id"]))
        if cursor:
            rows = [r for r in rows if r["document_id"] > cursor]
        page = rows[:limit]
        next_cursor = page[-1]["document_id"] if len(rows) > limit else None
        return [dict(r) for r in page], next_cursor

    def get_document_metadata(
        self,
        *,
        tenant_id: str,
        principal: str,
        document_id: str,
        collection_id: str | None = None,
        version_id: str | None = None,
    ) -> DocumentRow | None:
        principals, default_acls, grants = self._acl_context(tenant_id, principal)
        for doc in self._documents:
            if doc["tenant_id"] != tenant_id or doc["document_id"] != document_id:
                continue
            if collection_id and doc["collection_id"] != collection_id:
                continue
            if not self._allowed(doc, principals, default_acls, grants):
                return None
            row = dict(doc)
            if version_id:
                row["version_id"] = version_id
            row["acl"] = {
                "collection_secured": bool(
                    default_acls.get((tenant_id, doc["collection_id"]), [])
                ),
                "readable": True,
            }
            return row
        return None


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

    def _load_acl(
        self,
        conn,
        *,
        tenant_id: str,
        principal: str,
    ) -> tuple[set[str], dict[tuple[str, str], list[Any]], list[dict[str, Any]]]:
        cached = get_acl_entry(tenant_id=tenant_id, principal=principal)
        if cached:
            principals = set(cached["principals"])
            default_acls = {
                (tenant_id, collection_id): list(acl or [])
                for collection_id, acl in cached.get("default_acls", {}).items()
            }
            return principals, default_acls, list(cached.get("grants") or [])

        principals = principals_for_acl(
            AuthContext(tenant_id=tenant_id, principal=principal, permissions=[], auth_method="mcp_token")
        )
        default_acls: dict[tuple[str, str], list[Any]] = {}
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT collection_id, default_acl
                FROM collections
                WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            for collection_id, default_acl in cur.fetchall():
                default_acls[(tenant_id, collection_id)] = list(default_acl or [])

            cur.execute(
                """
                SELECT collection_id, document_id, principal, permission
                FROM acl_grants
                WHERE tenant_id = %s AND principal = ANY(%s)
                """,
                (tenant_id, list(principals)),
            )
            grants = [
                {
                    "collection_id": row[0],
                    "document_id": row[1],
                    "principal": row[2],
                    "permission": row[3],
                }
                for row in cur.fetchall()
            ]
        set_acl_entry(
            tenant_id=tenant_id,
            principal=principal,
            value={
                "principals": list(principals),
                "default_acls": {
                    collection_id: default_acls[(tenant_id, collection_id)]
                    for collection_id in {cid for _, cid in default_acls}
                },
                "grants": grants,
            },
        )
        return principals, default_acls, grants

    def _fetch_documents(
        self,
        conn,
        *,
        tenant_id: str,
        collection_id: str | None,
        document_id: str | None,
        limit: int,
        cursor: str | None,
    ) -> list[DocumentRow]:
        sql = """
            SELECT d.tenant_id, d.collection_id, d.document_id, d.title,
                   d.source_uri, d.source_system, d.latest_version_id,
                   COALESCE(v.version_id, d.latest_version_id) AS version_id,
                   COALESCE(v.chunk_count, 0) AS chunk_count,
                   COALESCE(v.ingested_at, d.updated_at) AS ingested_at
            FROM documents d
            LEFT JOIN document_versions v
              ON d.tenant_id = v.tenant_id
             AND d.collection_id = v.collection_id
             AND d.document_id = v.document_id
             AND v.version_id = COALESCE(d.latest_version_id, v.version_id)
            WHERE d.tenant_id = %s AND NOT d.tombstoned
        """
        params: list[Any] = [tenant_id]
        if collection_id:
            sql += " AND d.collection_id = %s"
            params.append(collection_id)
        if document_id:
            sql += " AND d.document_id = %s"
            params.append(document_id)
        if cursor:
            sql += " AND d.document_id > %s"
            params.append(cursor)
        sql += " ORDER BY d.collection_id, d.document_id LIMIT %s"
        params.append(limit + 1)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [
            {
                "tenant_id": row[0],
                "collection_id": row[1],
                "document_id": row[2],
                "title": row[3],
                "source_uri": row[4],
                "source_system": row[5],
                "latest_version_id": row[6],
                "version_id": row[7],
                "chunk_count": row[8],
                "ingested_at": row[9].isoformat() if isinstance(row[9], datetime) else row[9],
            }
            for row in rows
        ]

    def list_indexed_documents(
        self,
        *,
        tenant_id: str,
        principal: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[DocumentRow], str | None]:
        with self._connect() as conn:
            principals, default_acls, grants = self._load_acl(conn, tenant_id=tenant_id, principal=principal)
            candidates = self._fetch_documents(
                conn,
                tenant_id=tenant_id,
                collection_id=collection_id,
                document_id=document_id,
                limit=limit,
                cursor=cursor,
            )
        allowed = [
            doc
            for doc in candidates
            if can_read_document(
                principals,
                collection_id=doc["collection_id"],
                document_id=doc["document_id"],
                default_acl=default_acls.get((tenant_id, doc["collection_id"]), []),
                grants=grants,
            )
        ]
        page = allowed[:limit]
        next_cursor = allowed[limit]["document_id"] if len(allowed) > limit else None
        return page, next_cursor

    def get_document_metadata(
        self,
        *,
        tenant_id: str,
        principal: str,
        document_id: str,
        collection_id: str | None = None,
        version_id: str | None = None,
    ) -> DocumentRow | None:
        with self._connect() as conn:
            principals, default_acls, grants = self._load_acl(conn, tenant_id=tenant_id, principal=principal)
            candidates = self._fetch_documents(
                conn,
                tenant_id=tenant_id,
                collection_id=collection_id,
                document_id=document_id,
                limit=1,
                cursor=None,
            )
            if not candidates:
                return None
            doc = candidates[0]
            if not can_read_document(
                principals,
                collection_id=doc["collection_id"],
                document_id=doc["document_id"],
                default_acl=default_acls.get((tenant_id, doc["collection_id"]), []),
                grants=grants,
            ):
                return None
            if version_id:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT version_id, chunk_count, content_hash, ingested_at
                        FROM document_versions
                        WHERE tenant_id = %s AND collection_id = %s
                          AND document_id = %s AND version_id = %s
                        """,
                        (tenant_id, doc["collection_id"], document_id, version_id),
                    )
                    row = cur.fetchone()
                if row is None:
                    return None
                doc = {
                    **doc,
                    "version_id": row[0],
                    "chunk_count": row[1],
                    "content_hash": row[2],
                    "ingested_at": row[3].isoformat() if isinstance(row[3], datetime) else row[3],
                }
            doc["acl"] = {
                "collection_secured": bool(default_acls.get((tenant_id, doc["collection_id"]), [])),
                "readable": True,
            }
            return doc


def create_catalog_store(settings: Settings | None = None) -> CatalogStore:
    settings = settings or get_settings()
    if settings.catalog_dsn_ro:
        return PostgresCatalogStore(settings.catalog_dsn_ro)
    return InMemoryCatalogStore()
