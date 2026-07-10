"""RBAC permission matching."""

from __future__ import annotations

from app.models import AuthContext
from app.rbac import has_permission, require_permission
import pytest
from fastapi import HTTPException


def test_wildcard_admin() -> None:
    ctx = AuthContext("acme", "user:a", ["mcp.*"], "mcp_token")
    assert has_permission(ctx, "mcp.research")
    assert has_permission(ctx, "mcp.admin.tokens")


def test_forbidden_raises() -> None:
    ctx = AuthContext("acme", "user:a", ["mcp.catalog.read"], "mcp_token")
    with pytest.raises(HTTPException) as exc:
        require_permission(ctx, "mcp.research")
    assert exc.value.status_code == 403
