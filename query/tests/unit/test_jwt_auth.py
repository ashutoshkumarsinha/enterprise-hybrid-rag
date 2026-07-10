"""JWT validation and auth context."""

from __future__ import annotations

import os

import jwt
import pytest
from fastapi import HTTPException

from app.auth import resolve_auth_from_bearer
from app.jwt_auth import (
    JwtValidationError,
    permissions_from_claims,
    principal_from_claims,
    tenant_from_claims,
    validate_jwt,
)
from app.settings import Settings
from app.token_store import InMemoryTokenStore


def _settings(**kwargs) -> Settings:
    base = Settings(
        auth_required=False,
        jwt_bridge=True,
        oidc_issuer="http://keycloak/realms/hybrid-rag",
        jwks_uri="http://keycloak/certs",
    )
    return Settings(**{**base.__dict__, **kwargs})


def test_validate_jwt_stub_mode() -> None:
    os.environ["JWT_STUB"] = "true"
    token = jwt.encode(
        {
            "sub": "alice",
            "tenant_id": "acme",
            "realm_access": {"roles": ["user"]},
        },
        "secret",
        algorithm="HS256",
    )
    claims = validate_jwt(token, _settings())
    assert claims["sub"] == "alice"
    assert tenant_from_claims(claims, _settings()) == "acme"
    assert principal_from_claims(claims) == "user:alice"
    perms = permissions_from_claims(claims, _settings())
    assert "mcp.research" in perms


def test_resolve_auth_from_jwt() -> None:
    os.environ["JWT_STUB"] = "true"
    token = jwt.encode(
        {"sub": "bob", "tenant_id": "acme", "realm_access": {"roles": ["admin"]}},
        "secret",
        algorithm="HS256",
    )
    ctx = resolve_auth_from_bearer(
        token,
        settings=_settings(),
        token_store=InMemoryTokenStore(),
    )
    assert ctx.auth_method == "jwt"
    assert ctx.principal == "user:bob"
    assert "mcp.*" in ctx.permissions


def test_tenant_mismatch_rejected() -> None:
    os.environ["JWT_STUB"] = "true"
    token = jwt.encode(
        {"sub": "bob", "tenant_id": "acme", "realm_access": {"roles": ["user"]}},
        "secret",
        algorithm="HS256",
    )
    ctx = resolve_auth_from_bearer(
        token,
        settings=_settings(auth_required=True),
        token_store=InMemoryTokenStore(),
    )
    from app.auth import enforce_tenant_binding

    with pytest.raises(HTTPException) as exc:
        enforce_tenant_binding(ctx, {"tenant_id": "other"}, settings=_settings(auth_required=True))
    assert exc.value.status_code == 403


def test_missing_tenant_when_required() -> None:
    os.environ["JWT_STUB"] = "true"
    token = jwt.encode({"sub": "bob"}, "secret", algorithm="HS256")
    claims = validate_jwt(token, _settings(auth_required=True))
    with pytest.raises(JwtValidationError) as exc:
        tenant_from_claims(claims, _settings(auth_required=True))
    assert exc.value.code == "missing_tenant_claim"
