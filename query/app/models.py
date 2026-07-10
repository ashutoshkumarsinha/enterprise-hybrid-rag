"""Shared datatypes for hybrid-rag-query."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    """Resolved caller identity for RBAC and ACL."""

    tenant_id: str
    principal: str
    permissions: list[str]
    auth_method: str
    token_id: str | None = None
