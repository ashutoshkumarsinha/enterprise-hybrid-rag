"""OIDC JWT validation via JWKS — IF-6 · §9.2 · §7.13.6."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from app.settings import Settings, get_settings


class JwtValidationError(Exception):
    """JWT could not be validated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@lru_cache(maxsize=1)
def _jwks_client(jwks_uri: str) -> PyJWKClient:
    return PyJWKClient(jwks_uri, cache_keys=True, lifespan=300)


def validate_jwt(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Validate Bearer JWT and return claims."""
    settings = settings or get_settings()
    if os.environ.get("JWT_STUB", "").lower() in ("true", "1", "yes"):
        return jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )

    jwks_uri = settings.jwks_uri
    issuer = settings.oidc_issuer
    if not jwks_uri or not issuer:
        raise JwtValidationError("invalid_token", "JWKS or issuer not configured")

    try:
        client = _jwks_client(jwks_uri)
        signing_key = client.get_signing_key_from_jwt(token)
        decode_kwargs: dict[str, Any] = {
            "algorithms": ["RS256", "RS384", "RS512", "ES256"],
            "issuer": issuer,
        }
        if settings.jwt_audience:
            decode_kwargs["audience"] = settings.jwt_audience
        else:
            decode_kwargs["options"] = {"verify_aud": False}
        return jwt.decode(token, signing_key.key, **decode_kwargs)
    except InvalidTokenError as exc:
        message = str(exc).lower()
        if "issuer" in message:
            raise JwtValidationError("invalid_issuer", str(exc)) from exc
        if "audience" in message or "aud" in message:
            raise JwtValidationError("invalid_audience", str(exc)) from exc
        if "expired" in message:
            raise JwtValidationError("invalid_token", "token expired") from exc
        raise JwtValidationError("invalid_token", str(exc)) from exc
    except Exception as exc:
        raise JwtValidationError("invalid_token", str(exc)) from exc


def permissions_from_claims(claims: dict[str, Any], settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    roles = list(claims.get("realm_access", {}).get("roles", []) or [])
    resource_access = claims.get("resource_access") or {}
    for client_roles in resource_access.values():
        if isinstance(client_roles, dict):
            roles.extend(client_roles.get("roles", []) or [])

    permissions: set[str] = set()
    for role in roles:
        template = settings.role_templates.get(role)
        if template:
            permissions.update(template)
    if not permissions:
        permissions.update(settings.role_templates.get("user", []))
    return sorted(permissions)


def tenant_from_claims(claims: dict[str, Any], settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    tenant_id = claims.get("tenant_id")
    if tenant_id:
        return str(tenant_id)
    if settings.auth_required:
        raise JwtValidationError("missing_tenant_claim", "tenant_id claim required")
    return settings.default_tenant_id


def principal_from_claims(claims: dict[str, Any]) -> str:
    sub = claims.get("sub")
    if not sub:
        raise JwtValidationError("invalid_token", "missing sub claim")
    return f"user:{sub}"


def clear_jwks_cache() -> None:
    _jwks_client.cache_clear()
