"""FR-24 — JWT sub maps to catalog principal user:{sub}."""

from __future__ import annotations

import json
from pathlib import Path

import jwt
import pytest

from app.auth import resolve_auth_from_bearer
from app.jwt_auth import principal_from_claims, tenant_from_claims
from app.settings import Settings
from app.token_store import InMemoryTokenStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _settings(**overrides) -> Settings:
    base = Settings(
        auth_required=True,
        jwt_bridge=True,
        oidc_issuer="http://keycloak/realms/hybrid-rag",
        jwks_uri="http://keycloak/certs",
    )
    return Settings(**{**base.__dict__, **overrides})


def _encode_fixture(name: str) -> str:
    claims = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return jwt.encode(claims, "contract-secret", algorithm="HS256")


@pytest.mark.parametrize(
    ("fixture", "expected_principal", "expected_permission"),
    [
        ("jwt_viewer.json", "user:viewer-42", "mcp.catalog.read"),
        ("jwt_admin.json", "user:admin-7", "mcp.*"),
    ],
)
def test_jwt_sub_maps_to_principal(fixture: str, expected_principal: str, expected_permission: str) -> None:
    import os

    os.environ["JWT_STUB"] = "true"
    token = _encode_fixture(fixture)
    claims = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))

    assert principal_from_claims(claims) == expected_principal
    assert tenant_from_claims(claims, _settings()) == "acme"

    ctx = resolve_auth_from_bearer(
        token,
        settings=_settings(),
        token_store=InMemoryTokenStore(),
    )
    assert ctx.principal == expected_principal
    assert expected_permission in ctx.permissions
