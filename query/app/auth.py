"""Authentication helpers — MCP Bearer tokens, JWT bridge, and dev bypass.

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §7.10, §7.13, §9.2 · FR-23.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.jwt_auth import (
    JwtValidationError,
    permissions_from_claims,
    principal_from_claims,
    tenant_from_claims,
    validate_jwt,
)
from app.models import AuthContext
from app.settings import Settings, get_settings
from app.token_store import TokenStore, parse_mcp_token


def dev_bypass_context(settings: Settings) -> AuthContext:
    return AuthContext(
        tenant_id=settings.default_tenant_id,
        principal=settings.default_principal,
        permissions=["mcp.*"],
        auth_method="dev_bypass",
    )


def _http_error_from_jwt(exc: JwtValidationError) -> HTTPException:
    status = 403 if exc.code == "missing_tenant_claim" else 401
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


def resolve_auth_from_bearer(
    bearer: str | None,
    *,
    settings: Settings | None = None,
    token_store: TokenStore | None = None,
) -> AuthContext:
    """Build AuthContext from a raw Bearer token (HTTP, stdio, tests)."""
    settings = settings or get_settings()
    if token_store is None:
        from app.token_store import InMemoryTokenStore

        token_store = InMemoryTokenStore()

    if not bearer:
        if settings.auth_required:
            raise HTTPException(status_code=401, detail={"code": "auth", "message": "missing bearer"})
        return dev_bypass_context(settings)

    if bearer.startswith(settings.mcp_token_prefix):
        row = token_store.validate_access_token(bearer)
        if row is None:
            raise HTTPException(
                status_code=401,
                detail={"code": "auth", "message": "invalid or expired token"},
            )
        return AuthContext(
            tenant_id=row["tenant_id"],
            principal=row["principal"],
            permissions=list(row["permissions"]),
            auth_method="mcp_token",
            token_id=row["token_id"],
        )

    if settings.jwt_bridge:
        try:
            claims = validate_jwt(bearer, settings)
        except JwtValidationError as exc:
            raise _http_error_from_jwt(exc) from exc
        return AuthContext(
            tenant_id=tenant_from_claims(claims, settings),
            principal=principal_from_claims(claims),
            permissions=permissions_from_claims(claims, settings),
            auth_method="jwt",
        )

    raise HTTPException(status_code=401, detail={"code": "auth", "message": "unsupported bearer type"})


async def resolve_auth_context(
    request: Request,
    *,
    settings: Settings | None = None,
    token_store: TokenStore | None = None,
) -> AuthContext:
    """Build AuthContext from FastAPI request Authorization header."""
    settings = settings or get_settings()
    token_store = token_store or getattr(request.app.state, "token_store", None)
    if token_store is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "unavailable", "message": "token store"},
        )

    auth_header = request.headers.get("Authorization", "")
    bearer = None
    if auth_header.lower().startswith("bearer "):
        bearer = auth_header[7:].strip()
    return resolve_auth_from_bearer(bearer, settings=settings, token_store=token_store)


def enforce_tenant_binding(ctx: AuthContext, args: dict, *, settings: Settings | None = None) -> None:
    """Reject arg tenant_id that disagrees with auth context (§9.2)."""
    settings = settings or get_settings()
    arg_tenant = args.get("tenant_id")
    if not arg_tenant:
        return
    if arg_tenant != ctx.tenant_id:
        if settings.auth_required or ctx.auth_method in ("jwt", "mcp_token"):
            raise HTTPException(
                status_code=403,
                detail={"code": "tenant_mismatch", "message": "tenant_id mismatch"},
            )


def extract_bearer_token(authorization: str | None, prefix: str) -> tuple[str, str] | None:
    """Parse ``rag_mcp_{token_id}.{secret}`` from an Authorization header value."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return parse_mcp_token(authorization[7:].strip(), prefix)
