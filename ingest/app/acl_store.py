"""Catalog ACL grant administration — E-16."""

from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

_VALID_PERMISSIONS = frozenset({"read", "write", "admin"})


class AclStore(ABC):
    @abstractmethod
    def healthcheck(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def create_grant(
        self,
        *,
        tenant_id: str,
        principal: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        permission: str = "read",
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_grants(
        self,
        *,
        tenant_id: str,
        principal: str | None = None,
        collection_id: str | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete_grant(self, grant_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def set_collection_default_acl(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        default_acl: list[str],
    ) -> dict[str, Any]:
        raise NotImplementedError


def _validate_grant_input(
    *,
    tenant_id: str,
    principal: str,
    collection_id: str | None,
    document_id: str | None,
    permission: str,
) -> None:
    if not tenant_id or not principal:
        raise ValueError("tenant_id and principal are required")
    if not collection_id and not document_id:
        raise ValueError("collection_id or document_id is required")
    if permission not in _VALID_PERMISSIONS:
        raise ValueError(f"permission must be one of {sorted(_VALID_PERMISSIONS)}")


def _grant_row(
    *,
    grant_id: str,
    tenant_id: str,
    principal: str,
    collection_id: str | None,
    document_id: str | None,
    permission: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "grant_id": grant_id,
        "tenant_id": tenant_id,
        "principal": principal,
        "collection_id": collection_id,
        "document_id": document_id,
        "permission": permission,
        "created_at": created_at or datetime.now(UTC).isoformat(),
    }


class InMemoryAclStore(AclStore):
    """Dev/test ACL store when ``CATALOG_DSN`` is unset."""

    def __init__(self) -> None:
        self._grants: list[dict[str, Any]] = [
            _grant_row(
                grant_id="10000000-0000-4000-8000-000000000001",
                tenant_id="acme",
                principal="user:alice",
                collection_id="internal-only",
                document_id=None,
                permission="read",
                created_at="2026-01-10T08:00:00+00:00",
            )
        ]
        self._collections: dict[tuple[str, str], dict[str, Any]] = {
            ("acme", "payments-api"): {"default_acl": [], "display_name": "Payments API"},
            ("acme", "internal-only"): {
                "default_acl": ["user:alice"],
                "display_name": "Internal",
            },
        }

    def healthcheck(self) -> bool:
        return True

    def create_grant(
        self,
        *,
        tenant_id: str,
        principal: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        permission: str = "read",
    ) -> dict[str, Any]:
        _validate_grant_input(
            tenant_id=tenant_id,
            principal=principal,
            collection_id=collection_id,
            document_id=document_id,
            permission=permission,
        )
        grant = _grant_row(
            grant_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            principal=principal,
            collection_id=collection_id,
            document_id=document_id,
            permission=permission,
        )
        self._grants.append(grant)
        return grant

    def list_grants(
        self,
        *,
        tenant_id: str,
        principal: str | None = None,
        collection_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [g for g in self._grants if g["tenant_id"] == tenant_id]
        if principal:
            rows = [g for g in rows if g["principal"] == principal]
        if collection_id:
            rows = [g for g in rows if g.get("collection_id") == collection_id]
        return [dict(g) for g in rows]

    def delete_grant(self, grant_id: str) -> dict[str, Any] | None:
        for grant in self._grants:
            if grant["grant_id"] == grant_id:
                self._grants = [g for g in self._grants if g["grant_id"] != grant_id]
                return dict(grant)
        return None

    def set_collection_default_acl(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        default_acl: list[str],
    ) -> dict[str, Any]:
        key = (tenant_id, collection_id)
        row = self._collections.setdefault(
            key,
            {"display_name": collection_id, "default_acl": []},
        )
        row["default_acl"] = list(default_acl)
        return {
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "default_acl": list(default_acl),
            "display_name": row.get("display_name"),
        }


class PostgresAclStore(AclStore):
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

    def create_grant(
        self,
        *,
        tenant_id: str,
        principal: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        permission: str = "read",
    ) -> dict[str, Any]:
        _validate_grant_input(
            tenant_id=tenant_id,
            principal=principal,
            collection_id=collection_id,
            document_id=document_id,
            permission=permission,
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO acl_grants (
                        tenant_id, principal, collection_id, document_id, permission
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING grant_id, tenant_id, principal, collection_id,
                              document_id, permission, created_at
                    """,
                    (tenant_id, principal, collection_id, document_id, permission),
                )
                row = cur.fetchone()
            conn.commit()
        return {
            "grant_id": str(row[0]),
            "tenant_id": row[1],
            "principal": row[2],
            "collection_id": row[3],
            "document_id": row[4],
            "permission": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
        }

    def list_grants(
        self,
        *,
        tenant_id: str,
        principal: str | None = None,
        collection_id: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT grant_id, tenant_id, principal, collection_id,
                   document_id, permission, created_at
            FROM acl_grants
            WHERE tenant_id = %s
        """
        params: list[Any] = [tenant_id]
        if principal:
            sql += " AND principal = %s"
            params.append(principal)
        if collection_id:
            sql += " AND collection_id = %s"
            params.append(collection_id)
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [
            {
                "grant_id": str(row[0]),
                "tenant_id": row[1],
                "principal": row[2],
                "collection_id": row[3],
                "document_id": row[4],
                "permission": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
            }
            for row in rows
        ]

    def delete_grant(self, grant_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM acl_grants
                    WHERE grant_id = %s
                    RETURNING grant_id, tenant_id, principal, collection_id,
                              document_id, permission, created_at
                    """,
                    (grant_id,),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            return None
        return {
            "grant_id": str(row[0]),
            "tenant_id": row[1],
            "principal": row[2],
            "collection_id": row[3],
            "document_id": row[4],
            "permission": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
        }

    def set_collection_default_acl(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        default_acl: list[str],
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO collections (tenant_id, collection_id, default_acl)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (tenant_id, collection_id)
                    DO UPDATE SET default_acl = EXCLUDED.default_acl,
                                  updated_at = now()
                    RETURNING tenant_id, collection_id, default_acl, display_name
                    """,
                    (tenant_id, collection_id, json.dumps(default_acl)),
                )
                row = cur.fetchone()
            conn.commit()
        return {
            "tenant_id": row[0],
            "collection_id": row[1],
            "default_acl": list(row[2] or []),
            "display_name": row[3],
        }


_store: AclStore | None = None


def get_acl_store() -> AclStore:
    global _store
    if _store is None:
        dsn = os.environ.get("CATALOG_DSN")
        _store = PostgresAclStore(dsn) if dsn else InMemoryAclStore()
    return _store


def reset_acl_store() -> None:
    global _store
    _store = None
