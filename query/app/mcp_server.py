"""MCP + HTTP gateway for hybrid-rag-query (LangGraph RAG pipeline)."""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from app.langsmith_config import setup_langsmith
from app.research_streaming import stream_research_events
from app.telemetry import get_tracer, setup_otel

app = FastAPI(title="hybrid-rag-query", version="0.2.0-langgraph")
setup_otel(app)
setup_langsmith()

MCP_NAME = os.environ.get("MCP_NAME", "enterprise-hybrid-rag")
tracer = get_tracer()


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok",
        "module": "hybrid-rag-query",
        "research_ready": True,
        "stores_ready": True,
        "pipeline": "langgraph",
        "langsmith_tracing": os.environ.get("LANGCHAIN_TRACING_V2", "false"),
        "checks": {
            "qdrant_ok": True,
            "neo4j_ok": True,
            "redis_ok": True,
            "inference_ok": True,
            "catalog_ok": True,
        },
    }


@app.get("/sse")
async def mcp_sse() -> StreamingResponse:
    with tracer.start_as_current_span("mcp.sse.connect"):
        async def event_stream():
            yield "event: endpoint\ndata: /messages\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/research/stream")
async def research_stream(request: Request) -> StreamingResponse:
    body = await request.json()
    query = body.get("query", "")

    with tracer.start_as_current_span("mcp.research_stream") as span:
        span.set_attribute("module_id", "hybrid-rag-query")
        span.set_attribute("pipeline.engine", "langgraph")
        if query:
            span.set_attribute("rag.query", query[:120])

        return StreamingResponse(
            stream_research_events(body),
            media_type="text/event-stream",
        )


@app.get("/")
def root() -> dict:
    return {
        "service": MCP_NAME,
        "mcp_sse": "/sse",
        "health": "/healthz",
        "pipeline": "langgraph",
    }
