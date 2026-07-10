"""MCP access token persistence — mint, validate, revoke.

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §7.13.3 · query/docs/TOKEN_ADMIN.md.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

from app.rbac import expand_role_template
from app.settings import Settings, get_settings

TokenRow = dict[str, Any]


def parse_mcp_token(raw: str, prefix: str = "rag_mcp_") -> tuple[str, str] | None:
    if not raw.startswith(prefix):
        return None
    body = raw[len(prefix) :]
    if "." not in body:
        return None
    token_id, secret = body.split(".", 1)
    if not token_id or not secret:
        return None
    try:
        uuid.UUID(token_id)
    except ValueError:
        return None
    return token_id, secret


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


class TokenStore(ABC):
    @abstractmethod
    def mint(
        self,
        *,
        tenant_id: str,
        principal: str,
        label: str | None = None,
        role_template: str | None = None,
        permissions: list[str] | None = None,
        expires_in_days: int | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def validate_access_token(self, access_token: str) -> TokenRow | None:
        raise NotImplementedError

    @abstractmethod
    def list_tokens(
        self,
        *,
        tenant_id: str,
        principal: str | None = None,
        include_revoked: bool = False,
        limit: int = 50,
    ) -> list[TokenRow]:
        raise NotImplementedError

    @abstractmethod
    def revoke(self, token_id: str) -> TokenRow | None:
        raise NotImplementedError


class InMemoryTokenStore(TokenStore):
    """Dev/test token store when CATALOG_DSN_TOKEN is unset."""

    def __init__(self) -> None:
        self._rows: dict[str, TokenRow] = {}

    def mint(
        self,
        *,
        tenant_id: str,
        principal: str,
        label: str | None = None,
        role_template: str | None = None,
        permissions: list[str] | None = None,
        expires_in_days: int | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        token_id = str(uuid.uuid4())
        secret = secrets.token_urlsafe(24)
        if permissions is None:
            if not role_template:
                role_template = "user"
            permissions = expand_role_template(role_template, settings)
        ttl_days = expires_in_days if expires_in_days is not None else settings.token_default_ttl_days
        expires_at = _now() + timedelta(days=ttl_days)
        created_at = _now()
        row: TokenRow = {
            "token_id": token_id,
            "tenant_id": tenant_id,
            "principal": principal,
            "label": label,
            "permissions": permissions,
            "role_template": role_template,
            "secret_hash": _hash_secret(secret),
            "created_by": created_by,
            "created_at": created_at,
            "expires_at": expires_at,
            "revoked_at": None,
            "last_used_at": None,
        }
        self._rows[token_id] = row
        return {
            "token_id": token_id,
            "access_token": f"{settings.mcp_token_prefix}{token_id}.{secret}",
            "tenant_id": tenant_id,
            "principal": principal,
            "permissions": permissions,
            "expires_at": expires_at.isoformat(),
            "created_at": created_at.isoformat(),
        }

    def validate_access_token(self, access_token: str) -> TokenRow | None:
        settings = get_settings()
        parsed = parse_mcp_token(access_token, settings.mcp_token_prefix)
        if parsed is None:
            return None
        token_id, secret = parsed
        row = self._rows.get(token_id)
        if row is None:
            return None
        if row.get("revoked_at") is not None:
            return None
        expires_at = row.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at < _now():
            return None
        if not hmac.compare_digest(row["secret_hash"], _hash_secret(secret)):
            return None
        row["last_used_at"] = _now()
        return row

    def list_tokens(
        self,
        *,
        tenant_id: str,
        principal: str | None = None,
        include_revoked: bool = False,
        limit: int = 50,
    ) -> list[TokenRow]:
        rows = [r for r in self._rows.values() if r["tenant_id"] == tenant_id]
        if principal:
            rows = [r for r in rows if r["principal"] == principal]
        if not include_revoked:
            rows = [r for r in rows if r.get("revoked_at") is None]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return [_public_row(r) for r in rows[:limit]]

    def revoke(self, token_id: str) -> TokenRow | None:
        row = self._rows.get(token_id)
        if row is None:
            return None
        row["revoked_at"] = _now()
        return {"token_id": token_id, "revoked_at": row["revoked_at"].isoformat()}


class PostgresTokenStore(TokenStore):
    """Production token store backed by mcp_access_tokens."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn)

    def mint(
        self,
        *,
        tenant_id: str,
        principal: str,
        label: str | None = None,
        role_template: str | None = None,
        permissions: list[str] | None = None,
        expires_in_days: int | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        token_id = str(uuid.uuid4())
        secret = secrets.token_urlsafe(24)
        if permissions is None:
            if not role_template:
                role_template = "user"
            permissions = expand_role_template(role_template, settings)
        ttl_days = expires_in_days if expires_in_days is not None else settings.token_default_ttl_days
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mcp_access_tokens (
                        token_id, tenant_id, principal, label, permissions,
                        role_template, secret_hash, created_by, expires_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, now() + (%s || ' days')::interval)
                    RETURNING created_at, expires_at
                    """,
                    (
                        token_id,
                        tenant_id,
                        principal,
                        label,
                        _json_permissions(permissions),
                        role_template,
                        _hash_secret(secret),
                        created_by,
                        str(ttl_days),
                    ),
                )
                created_at, expires_at = cur.fetchone()
            conn.commit()
        return {
            "token_id": token_id,
            "access_token": f"{settings.mcp_token_prefix}{token_id}.{secret}",
            "tenant_id": tenant_id,
            "principal": principal,
            "permissions": permissions,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": created_at.isoformat() if created_at else None,
        }

    def validate_access_token(self, access_token: str) -> TokenRow | None:
        settings = get_settings()
        parsed = parse_mcp_token(access_token, settings.mcp_token_prefix)
        if parsed is None:
            return None
        token_id, secret = parsed
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT token_id, tenant_id, principal, permissions, expires_at, revoked_at, secret_hash
                    FROM mcp_access_tokens
                    WHERE token_id = %s
                    """,
                    (token_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                (
                    tid,
                    tenant_id,
                    principal,
                    permissions,
                    expires_at,
                    revoked_at,
                    secret_hash,
                ) = row
                if revoked_at is not None:
                    return None
                if expires_at is not None and expires_at < _now():
                    return None
                if not hmac.compare_digest(secret_hash, _hash_secret(secret)):
                    return None
                cur.execute(
                    "UPDATE mcp_access_tokens SET last_used_at = now() WHERE token_id = %s",
                    (token_id,),
                )
            conn.commit()
        return {
            "token_id": str(tid),
            "tenant_id": tenant_id,
            "principal": principal,
            "permissions": permissions if isinstance(permissions, list) else list(permissions),
        }

    def list_tokens(
        self,
        *,
        tenant_id: str,
        principal: str | None = None,
        include_revoked: bool = False,
        limit: int = 50,
    ) -> list[TokenRow]:
        clauses = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if principal:
            clauses.append("principal = %s")
            params.append(principal)
        if not include_revoked:
            clauses.append("revoked_at IS NULL")
        sql = f"""
            SELECT token_id, tenant_id, principal, label, permissions, role_template,
                   created_at, expires_at, revoked_at, last_used_at
            FROM mcp_access_tokens
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(limit)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [
            _public_row(
                {
                    "token_id": str(r[0]),
                    "tenant_id": r[1],
                    "principal": r[2],
                    "label": r[3],
                    "permissions": r[4] if isinstance(r[4], list) else list(r[4]),
                    "role_template": r[5],
                    "created_at": r[6],
                    "expires_at": r[7],
                    "revoked_at": r[8],
                    "last_used_at": r[9],
                }
            )
            for r in rows
        ]

    def revoke(self, token_id: str) -> TokenRow | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE mcp_access_tokens
                    SET revoked_at = now()
                    WHERE token_id = %s AND revoked_at IS NULL
                    RETURNING revoked_at
                    """,
                    (token_id,),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            return None
        return {"token_id": token_id, "revoked_at": row[0].isoformat()}


def _json_permissions(permissions: list[str]) -> str:
    import json

    return json.dumps(permissions)


def _public_row(row: TokenRow) -> TokenRow:
    created_at = row.get("created_at")
    expires_at = row.get("expires_at")
    revoked_at = row.get("revoked_at")
    last_used_at = row.get("last_used_at")
    return {
        "token_id": row["token_id"],
        "tenant_id": row["tenant_id"],
        "principal": row["principal"],
        "label": row.get("label"),
        "permissions": row.get("permissions", []),
        "role_template": row.get("role_template"),
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at,
        "revoked_at": revoked_at.isoformat() if isinstance(revoked_at, datetime) else revoked_at,
        "last_used_at": last_used_at.isoformat() if isinstance(last_used_at, datetime) else last_used_at,
    }


def create_token_store(settings: Settings | None = None) -> TokenStore:
    settings = settings or get_settings()
    if settings.catalog_dsn_token:
        return PostgresTokenStore(settings.catalog_dsn_token)
    return InMemoryTokenStore()
