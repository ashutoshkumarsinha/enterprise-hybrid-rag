"""MCP stdio transport for Cursor / Claude Desktop hosts.

Spec: §7.1.1 · Env ``MCP_ACCESS_TOKEN`` or ``JWT_STUB`` / dev bypass.

Launch:
  MCP_ACCESS_TOKEN=rag_mcp_... python -m app.mcp_stdio
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.auth import resolve_auth_from_bearer
from app.mcp_tools import dispatch_tool, list_tool_definitions
from app.session_store import create_session_store
from app.settings import get_settings
from app.token_store import create_token_store
from app.warmup_clients import warmup_clients

SERVER_NAME = os.environ.get("MCP_NAME", "enterprise-hybrid-rag")
SERVER_VERSION = os.environ.get("MCP_VERSION", "1.0.0")

_server = Server(SERVER_NAME)
_settings = get_settings()
_token_store = create_token_store(_settings)
_session_store = create_session_store(_settings)


def _auth_context() -> Any:
    bearer = os.environ.get("MCP_ACCESS_TOKEN") or os.environ.get("AUTHORIZATION", "").removeprefix(
        "Bearer "
    ).strip()
    return resolve_auth_from_bearer(
        bearer or None,
        settings=_settings,
        token_store=_token_store,
    )


@_server.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name=item["name"],
            description=item["description"],
            inputSchema=item["inputSchema"],
        )
        for item in list_tool_definitions()
    ]


@_server.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    args = arguments or {}
    try:
        ctx = _auth_context()
        result = await dispatch_tool(
            name,
            args,
            ctx=ctx,
            session_store=_session_store,
            settings=_settings,
        )
        if isinstance(result, str):
            text = result
        else:
            text = json.dumps(result, indent=2)
        return [TextContent(type="text", text=text)]
    except Exception as exc:
        if hasattr(exc, "status_code"):
            detail = getattr(exc, "detail", str(exc))
            text = json.dumps(detail) if isinstance(detail, dict) else str(detail)
            return [TextContent(type="text", text=f"error: {text}")]
        return [TextContent(type="text", text=f"error: {exc}")]


async def run_stdio_server() -> None:
    warmup_clients()
    async with stdio_server() as (read_stream, write_stream):
        await _server.run(
            read_stream,
            write_stream,
            _server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
