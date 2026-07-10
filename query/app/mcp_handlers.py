"""MCP tool and HTTP handler logic for hybrid-rag-query."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.models import AuthContext
from app.mcp_format import format_research_markdown
from app.rag_graph import run_rag_pipeline
from app.rag_state import RAGState
from app.rbac import require_tool
from app.session_store import SessionStore
from app.settings import Settings, get_settings


def _tenant_id(ctx: AuthContext, args: dict[str, Any]) -> str:
    return args.get("tenant_id") or ctx.tenant_id


async def handle_research_documents(
    args: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run RAG pipeline and return markdown per §7.8."""
    settings = settings or get_settings()
    require_tool(ctx, "research_documents", settings=settings)

    tenant_id = _tenant_id(ctx, args)
    session_id = args.get("session_id")
    history: list[dict[str, str]] = []
    if settings.sessions_enabled and session_id:
        session = session_store.get_session(
            session_id, tenant_id=tenant_id, principal=ctx.principal
        )
        if session is None and not args.get("create_session_if_missing"):
            raise HTTPException(status_code=404, detail={"code": "session_not_found"})
        if session is not None:
            history = session_store.load_history(
                session_id,
                tenant_id=tenant_id,
                principal=ctx.principal,
                max_turns=settings.max_history_turns,
            )

    explicit = bool(args.get("document_id") or args.get("collection_id"))
    state = RAGState(
        query=args.get("query", ""),
        tenant_id=tenant_id,
        collection_id=args.get("collection_id") or "",
        document_id=args.get("document_id"),
        version_id=args.get("version_id"),
        explicit_scope=explicit,
        skip_supervisor=explicit,
        request_id=args.get("request_id"),
        langfuse_session_id=args.get("langfuse_session_id") or session_id,
        langfuse_trace_id=args.get("langfuse_trace_id"),
        session_id=session_id,
        conversation_history=history,
        graph_enrich_enabled=True,
        timings_ms={},
        from_cache=False,
        abstained=False,
    )
    final = await run_rag_pipeline(state)
    markdown = format_research_markdown(final)

    if settings.sessions_enabled and session_id and final.get("answer_text"):
        try:
            session_store.append_turn(
                session_id,
                tenant_id=tenant_id,
                principal=ctx.principal,
                user_content=args.get("query", ""),
                assistant_content=final.get("answer_text", ""),
                rag_metadata={
                    "sources": final.get("sources") or [],
                    "timings_ms": final.get("timings_ms") or {},
                    "stub": final.get("stub", True),
                },
            )
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "session_not_found"}) from None

    return {"markdown": markdown, "stub": final.get("stub", True)}


def handle_create_session(
    args: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    require_tool(ctx, "create_conversation_session", settings=settings)
    if not settings.sessions_enabled:
        raise HTTPException(status_code=400, detail={"code": "sessions_disabled"})
    row = session_store.create_session(
        tenant_id=_tenant_id(ctx, args),
        principal=ctx.principal,
        title=args.get("title"),
        collection_id=args.get("collection_id"),
        document_id=args.get("document_id"),
        version_id=args.get("version_id"),
        metadata=args.get("metadata"),
    )
    return {"session_id": row["session_id"], "created_at": row["created_at"]}


def handle_list_sessions(
    args: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    require_tool(ctx, "list_conversation_sessions", settings=settings)
    items = session_store.list_sessions(
        tenant_id=_tenant_id(ctx, args),
        principal=ctx.principal,
        limit=min(int(args.get("limit", 20)), 100),
        include_deleted=bool(args.get("include_deleted", False)),
    )
    return {"items": items, "next_cursor": None}


def handle_get_history(
    args: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    require_tool(ctx, "get_conversation_history", settings=settings)
    session_id = args.get("session_id")
    if not session_id:
        raise HTTPException(status_code=422, detail={"code": "validation", "message": "session_id"})
    messages = session_store.get_history(
        session_id,
        tenant_id=_tenant_id(ctx, args),
        principal=ctx.principal,
        limit=min(int(args.get("limit", 50)), 200),
    )
    if not messages and session_store.get_session(
        session_id, tenant_id=_tenant_id(ctx, args), principal=ctx.principal
    ) is None:
        raise HTTPException(status_code=404, detail={"code": "session_not_found"})
    return {"session_id": session_id, "messages": messages}
