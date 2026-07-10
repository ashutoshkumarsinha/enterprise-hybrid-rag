"""MCP + HTTP gateway for hybrid-rag-query (LangGraph RAG pipeline)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.models import AuthContext
from app.deps import get_auth_context
from app.langsmith_config import setup_langsmith
from app.catalog_store import create_catalog_store
from app.catalog_handlers import (
    handle_get_document_metadata,
    handle_list_indexed_documents,
    handle_visualize_document_graph,
)
from app.mcp_handlers import (
    handle_create_session,
    handle_get_history,
    handle_list_sessions,
    handle_research_documents,
)
from app.rbac import require_permission
from app.research_streaming import stream_research_events
from app.session_store import create_session_store
from app.settings import get_settings
from app.telemetry import get_tracer, setup_otel
from app.token_store import create_token_store
from app.warmup_clients import warmup_clients

MCP_NAME = os.environ.get("MCP_NAME", "enterprise-hybrid-rag")
tracer = get_tracer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.token_store = create_token_store(settings)
    app.state.session_store = create_session_store(settings)
    app.state.catalog_store = create_catalog_store(settings)
    warmup_clients()
    yield


app = FastAPI(title="hybrid-rag-query", version="0.3.0-langgraph", lifespan=lifespan)
setup_otel(app)
setup_langsmith()


@app.get("/healthz")
def healthz():
    settings = get_settings()
    from app.client_factory import (
        breaker_snapshots,
        get_chat_client,
        get_embed_client,
        get_neo4j_client,
        get_qdrant_client,
        get_reranker_client,
    )
    from app.catalog_store import create_catalog_store
    from app.query_cache import redis_healthcheck

    qdrant_ok = get_qdrant_client().healthcheck()
    embed_ok = get_embed_client().healthcheck()
    chat_ok = get_chat_client().healthcheck()
    reranker_ok = get_reranker_client().healthcheck()
    neo4j_ok = True if settings.stub_health else get_neo4j_client().healthcheck()
    catalog_ok = True if settings.stub_health else create_catalog_store(settings).healthcheck()
    redis_ok = True if settings.stub_health else redis_healthcheck()
    if settings.stub_health:
        stores_ready = True
        research_ready = True
    else:
        stores_ready = qdrant_ok and embed_ok and chat_ok and reranker_ok and catalog_ok
        research_ready = stores_ready
    status = "ok" if research_ready else "degraded"
    body = {
        "status": status,
        "module": "hybrid-rag-query",
        "research_ready": research_ready,
        "stores_ready": stores_ready,
        "pipeline": "langgraph",
        "langsmith_tracing": os.environ.get("LANGCHAIN_TRACING_V2", "false"),
        "checks": {
            "qdrant_ok": qdrant_ok,
            "neo4j_ok": neo4j_ok,
            "redis_ok": redis_ok,
            "inference_ok": embed_ok and chat_ok,
            "catalog_ok": catalog_ok,
            "reranker_ok": reranker_ok,
        },
        "circuit_breakers": breaker_snapshots(),
    }
    if not research_ready:
        return JSONResponse(status_code=503, content=body)
    return body


@app.get("/sse")
async def mcp_sse() -> StreamingResponse:
    with tracer.start_as_current_span("mcp.sse.connect"):
        async def event_stream():
            yield "event: endpoint\ndata: /messages\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/research/stream")
async def research_stream(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> StreamingResponse:
    require_permission(ctx, "mcp.research")
    body = await request.json()

    with tracer.start_as_current_span("mcp.research_stream") as span:
        query = body.get("query", "")
        span.set_attribute("module_id", "hybrid-rag-query")
        span.set_attribute("pipeline.engine", "langgraph")
        if query:
            span.set_attribute("rag.query", query[:120])

        return StreamingResponse(
            stream_research_events(
                body,
                ctx=ctx,
                session_store=request.app.state.session_store,
            ),
            media_type="text/event-stream",
        )


@app.post("/mcp/tools/research_documents")
async def mcp_research_documents(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return await handle_research_documents(
        body,
        ctx=ctx,
        session_store=request.app.state.session_store,
        settings=request.app.state.settings,
    )


@app.post("/mcp/tools/create_conversation_session")
async def mcp_create_session(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return handle_create_session(
        body, ctx=ctx, session_store=request.app.state.session_store, settings=request.app.state.settings
    )


@app.post("/mcp/tools/list_conversation_sessions")
async def mcp_list_sessions(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return handle_list_sessions(
        body, ctx=ctx, session_store=request.app.state.session_store, settings=request.app.state.settings
    )


@app.post("/mcp/tools/get_conversation_history")
async def mcp_get_history(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return handle_get_history(
        body, ctx=ctx, session_store=request.app.state.session_store, settings=request.app.state.settings
    )


@app.post("/mcp/tools/list_indexed_documents")
async def mcp_list_indexed_documents(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return handle_list_indexed_documents(
        body,
        ctx=ctx,
        catalog_store=request.app.state.catalog_store,
        settings=request.app.state.settings,
    )


@app.post("/mcp/tools/get_document_metadata")
async def mcp_get_document_metadata(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return handle_get_document_metadata(
        body,
        ctx=ctx,
        catalog_store=request.app.state.catalog_store,
        settings=request.app.state.settings,
    )


@app.post("/mcp/tools/visualize_document_graph")
async def mcp_visualize_document_graph(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return handle_visualize_document_graph(
        body,
        ctx=ctx,
        catalog_store=request.app.state.catalog_store,
        settings=request.app.state.settings,
    )


@app.post("/sessions")
async def http_create_session(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    body = await request.json()
    return handle_create_session(
        body, ctx=ctx, session_store=request.app.state.session_store, settings=request.app.state.settings
    )


@app.get("/sessions")
async def http_list_sessions(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    args = dict(request.query_params)
    return handle_list_sessions(
        args, ctx=ctx, session_store=request.app.state.session_store, settings=request.app.state.settings
    )


@app.get("/sessions/{session_id}/messages")
async def http_session_messages(
    session_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    args = {"session_id": session_id, **dict(request.query_params)}
    return handle_get_history(
        args, ctx=ctx, session_store=request.app.state.session_store, settings=request.app.state.settings
    )


@app.post("/admin/mcp/tokens")
async def admin_mint_token(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    settings = request.app.state.settings
    body = await request.json()
    if settings.auth_required or not settings.allow_token_bootstrap:
        require_permission(ctx, "mcp.admin.tokens", settings=settings)
    elif ctx.auth_method == "dev_bypass" and not settings.allow_token_bootstrap:
        require_permission(ctx, "mcp.admin.tokens", settings=settings)

    tenant_id = body.get("tenant_id")
    principal = body.get("principal")
    if not tenant_id or not principal:
        raise HTTPException(status_code=422, detail={"code": "validation"})

    result = request.app.state.token_store.mint(
        tenant_id=tenant_id,
        principal=principal,
        label=body.get("label"),
        role_template=body.get("role_template"),
        permissions=body.get("permissions"),
        expires_in_days=body.get("expires_in_days"),
        created_by=ctx.principal,
    )
    return result


@app.get("/admin/mcp/tokens")
async def admin_list_tokens(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    require_permission(ctx, "mcp.admin.tokens")
    tenant_id = request.query_params.get("tenant_id") or ctx.tenant_id
    items = request.app.state.token_store.list_tokens(
        tenant_id=tenant_id,
        principal=request.query_params.get("principal"),
        include_revoked=request.query_params.get("include_revoked", "false").lower() == "true",
        limit=min(int(request.query_params.get("limit", 50)), 200),
    )
    return {"items": items, "next_cursor": None}


@app.post("/admin/mcp/tokens/{token_id}/revoke")
async def admin_revoke_token(
    token_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    require_permission(ctx, "mcp.admin.tokens")
    result = request.app.state.token_store.revoke(token_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "token_not_found"})
    return result


@app.get("/")
def root() -> dict:
    return {
        "service": MCP_NAME,
        "mcp_sse": "/sse",
        "health": "/healthz",
        "pipeline": "langgraph",
        "mcp_tools": "/mcp/tools/{tool_name}",
    }
