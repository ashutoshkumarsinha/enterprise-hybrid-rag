"""Environment-backed settings for hybrid-rag-query."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration from environment variables."""

    auth_required: bool = False
    jwt_bridge: bool = True
    rbac_enabled: bool = True
    mcp_token_prefix: str = "rag_mcp_"
    allow_token_bootstrap: bool = False
    default_tenant_id: str = "dev"
    default_principal: str = "user:dev"

    sessions_enabled: bool = True
    max_history_turns: int = 10
    token_default_ttl_days: int = 90

    catalog_dsn_token: str | None = None
    catalog_dsn_session: str | None = None
    stub_health: bool = True

    role_templates: dict[str, list[str]] = field(
        default_factory=lambda: {
            "viewer": [
                "mcp.catalog.read",
                "mcp.graph.read",
                "mcp.session.read",
            ],
            "user": [
                "mcp.catalog.read",
                "mcp.graph.read",
                "mcp.session",
                "mcp.research",
            ],
            "collection-admin": [
                "mcp.catalog.read",
                "mcp.graph.read",
                "mcp.session",
                "mcp.research",
                "mcp.admin",
            ],
            "admin": ["mcp.*"],
        }
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        auth_required=_env_bool("AUTH_REQUIRED", False),
        jwt_bridge=_env_bool("JWT_BRIDGE", True),
        rbac_enabled=_env_bool("RBAC_ENABLED", True),
        mcp_token_prefix=os.environ.get("MCP_TOKEN_PREFIX", "rag_mcp_"),
        allow_token_bootstrap=_env_bool("ALLOW_TOKEN_BOOTSTRAP", False),
        default_tenant_id=os.environ.get("DEFAULT_TENANT_ID", "dev"),
        default_principal=os.environ.get("DEFAULT_PRINCIPAL", "user:dev"),
        sessions_enabled=_env_bool("SESSIONS_ENABLED", True),
        max_history_turns=_env_int("SESSIONS_MAX_HISTORY_TURNS", 10),
        token_default_ttl_days=_env_int("TOKEN_DEFAULT_TTL_DAYS", 90),
        catalog_dsn_token=os.environ.get("CATALOG_DSN_TOKEN"),
        catalog_dsn_session=os.environ.get("CATALOG_DSN_SESSION"),
        stub_health=_env_bool("STUB_HEALTH", True),
    )
