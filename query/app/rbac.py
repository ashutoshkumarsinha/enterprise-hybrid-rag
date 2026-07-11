"""RBAC permission checks for MCP tools and HTTP routes.

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §7.13 · query/docs/RBAC.md.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.models import AuthContext
from app.settings import Settings, get_settings
from app.telemetry import SPAN_MCP_AUTHZ_CHECK, start_span

TOOL_PERMISSIONS: dict[str, str] = {
    "research_documents": "mcp.research",
    "list_indexed_documents": "mcp.catalog.read",
    "get_document_metadata": "mcp.catalog.read",
    "visualize_document_graph": "mcp.graph.read",
    "create_conversation_session": "mcp.session.write",
    "list_conversation_sessions": "mcp.session.read",
    "get_conversation_history": "mcp.session.read",
    "update_conversation_session": "mcp.session.write",
    "delete_conversation_session": "mcp.session.write",
    "list_collections": "mcp.admin.collections",
    "search_snippets": "mcp.admin.diagnostics",
    "explain_scope": "mcp.admin.diagnostics",
    "mint_mcp_token": "mcp.admin.tokens",
    "list_mcp_tokens": "mcp.admin.tokens",
    "revoke_mcp_token": "mcp.admin.tokens",
}

ROUTE_PERMISSIONS: dict[str, str] = {
    "POST /research/stream": "mcp.research",
    "POST /sessions": "mcp.session.write",
    "GET /sessions": "mcp.session.read",
    "GET /sessions/{session_id}": "mcp.session.read",
    "GET /sessions/{session_id}/messages": "mcp.session.read",
    "PATCH /sessions/{session_id}": "mcp.session.write",
    "DELETE /sessions/{session_id}": "mcp.session.write",
    "POST /admin/mcp/tokens": "mcp.admin.tokens",
    "GET /admin/mcp/tokens": "mcp.admin.tokens",
    "POST /admin/mcp/tokens/{token_id}/revoke": "mcp.admin.tokens",
}


def expand_role_template(template: str, settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    perms = settings.role_templates.get(template)
    if perms is None:
        raise ValueError(f"unknown role_template: {template}")
    return list(perms)


def has_permission(ctx: AuthContext, permission: str, *, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.rbac_enabled:
        return True
    granted = set(ctx.permissions)
    if "mcp.*" in granted:
        return True
    if permission in granted:
        return True
    parts = permission.split(".")
    for i in range(len(parts), 1, -1):
        wildcard = ".".join(parts[: i - 1]) + ".*"
        if wildcard in granted:
            return True
    parent = permission.rsplit(".", 1)[0]
    if parent in ("mcp.session", "mcp.admin") and f"{parent}.*" in granted:
        return True
    if parent == "mcp.session" and "mcp.session" in granted:
        return True
    if parent == "mcp.admin" and "mcp.admin" in granted:
        return True
    return False


def require_permission(
    ctx: AuthContext,
    permission: str,
    *,
    settings: Settings | None = None,
) -> None:
    with start_span(SPAN_MCP_AUTHZ_CHECK) as span:
        span.set_attribute("authz.permission", permission)
        allowed = has_permission(ctx, permission, settings=settings)
        span.set_attribute("authz.allowed", allowed)
        if not allowed:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": permission})


def require_tool(ctx: AuthContext, tool_name: str, *, settings: Settings | None = None) -> None:
    permission = TOOL_PERMISSIONS.get(tool_name)
    if permission is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": tool_name})
    require_permission(ctx, permission, settings=settings)
