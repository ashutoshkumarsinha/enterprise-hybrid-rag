"""Authentication helpers — MCP Bearer tokens and optional dev bypass.

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §7.10, §7.13 · FR-23.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.models import AuthContext
from app.settings import Settings, get_settings
from app.token_store import parse_mcp_token


def dev_bypass_context(settings: Settings) -> AuthContext:
    return AuthContext(
        tenant_id=settings.default_tenant_id,
        principal=settings.default_principal,
        permissions=["mcp.*"],
        auth_method="dev_bypass",
    )


async def resolve_auth_context(
    request: Request,
    *,
    settings: Settings | None = None,
    token_store: TokenStore | None = None,
) -> AuthContext:
    """Build AuthContext from Authorization header or dev bypass."""
    settings = settings or get_settings()
    token_store = token_store or getattr(request.app.state, "token_store", None)
    if token_store is None:
        raise HTTPException(status_code=503, detail={"code": "unavailable", "message": "token store"})

    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        if settings.auth_required:
            raise HTTPException(status_code=401, detail={"code": "auth", "message": "missing bearer"})
        return dev_bypass_context(settings)

    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "auth", "message": "invalid authorization"})

    bearer = auth_header[7:].strip()
    if bearer.startswith(settings.mcp_token_prefix):
        row = token_store.validate_access_token(bearer)
        if row is None:
            raise HTTPException(status_code=401, detail={"code": "auth", "message": "invalid or expired token"})
        return AuthContext(
            tenant_id=row["tenant_id"],
            principal=row["principal"],
            permissions=list(row["permissions"]),
            auth_method="mcp_token",
            token_id=row["token_id"],
        )

    if settings.jwt_bridge:
        # Stub: production validates JWKS (§7.13.6). Dev accepts opaque bearer as principal hint.
        principal = f"user:{bearer[:64]}" if bearer else settings.default_principal
        permissions = settings.role_templates.get("user", [])
        return AuthContext(
            tenant_id=settings.default_tenant_id,
            principal=principal,
            permissions=permissions,
            auth_method="jwt_stub",
        )

    raise HTTPException(status_code=401, detail={"code": "auth", "message": "unsupported bearer type"})


def extract_bearer_token(authorization: str | None, prefix: str) -> tuple[str, str] | None:
    """Parse ``rag_mcp_{token_id}.{secret}`` from an Authorization header value."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return parse_mcp_token(authorization[7:].strip(), prefix)
