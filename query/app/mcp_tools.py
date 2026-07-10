"""MCP tool metadata and dispatch for HTTP + stdio transports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.auth import enforce_tenant_binding
from app.mcp_handlers import (
    handle_create_session,
    handle_get_history,
    handle_list_sessions,
    handle_research_documents,
)
from app.models import AuthContext
from app.session_store import SessionStore
from app.settings import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "modules" / "schemas"

TOOL_SCHEMA_FILES: dict[str, str] = {
    "research_documents": "mcp_research_documents.input.v1.json",
    "create_conversation_session": "mcp_create_conversation_session.input.v1.json",
    "get_conversation_history": "mcp_get_conversation_history.input.v1.json",
    "list_conversation_sessions": "mcp_list_conversation_sessions.input.v1.json",
    "list_indexed_documents": "mcp_list_indexed_documents.input.v1.json",
    "get_document_metadata": "mcp_get_document_metadata.input.v1.json",
    "visualize_document_graph": "mcp_visualize_document_graph.input.v1.json",
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "research_documents": "Run grounded RAG over ingested documents",
    "create_conversation_session": "Create a persisted MCP conversation session",
    "list_conversation_sessions": "List conversation sessions for the current principal",
    "get_conversation_history": "Load messages for a conversation session",
    "list_indexed_documents": "List documents in the catalog (stub)",
    "get_document_metadata": "Fetch document metadata (stub)",
    "visualize_document_graph": "Render document graph as Mermaid (stub)",
}


def load_tool_input_schema(tool_name: str) -> dict[str, Any]:
    filename = TOOL_SCHEMA_FILES.get(tool_name)
    if not filename:
        return {"type": "object", "properties": {}}
    path = SCHEMAS_DIR / filename
    if not path.exists():
        return {"type": "object", "properties": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def list_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": TOOL_DESCRIPTIONS.get(name, name),
            "inputSchema": load_tool_input_schema(name),
        }
        for name in TOOL_SCHEMA_FILES
    ]


async def dispatch_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore,
    settings: Settings | None = None,
) -> Any:
    settings = settings or get_settings()
    enforce_tenant_binding(ctx, arguments, settings=settings)

    if tool_name == "research_documents":
        result = await handle_research_documents(
            arguments, ctx=ctx, session_store=session_store, settings=settings
        )
        return result.get("markdown", "")
    if tool_name == "create_conversation_session":
        return handle_create_session(arguments, ctx=ctx, session_store=session_store, settings=settings)
    if tool_name == "list_conversation_sessions":
        return handle_list_sessions(arguments, ctx=ctx, session_store=session_store, settings=settings)
    if tool_name == "get_conversation_history":
        return handle_get_history(arguments, ctx=ctx, session_store=session_store, settings=settings)
    if tool_name in ("list_indexed_documents", "get_document_metadata", "visualize_document_graph"):
        return {
            "stub": True,
            "message": f"{tool_name} not yet implemented",
            "arguments": arguments,
        }

    raise HTTPException(status_code=404, detail={"code": "not_found", "message": tool_name})
