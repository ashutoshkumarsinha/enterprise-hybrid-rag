"""SSE streaming for POST /research/stream — backed by LangGraph pipeline."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.rag_graph import run_rag_pipeline
from app.rag_state import RAGState


def state_from_request(body: dict[str, Any]) -> RAGState:
    explicit = bool(body.get("document_id") or body.get("collection_id"))
    return RAGState(
        query=body.get("query", ""),
        tenant_id=body.get("tenant_id", ""),
        collection_id=body.get("collection_id", ""),
        document_id=body.get("document_id"),
        version_id=body.get("version_id"),
        explicit_scope=explicit,
        skip_supervisor=explicit,
        request_id=body.get("request_id"),
        langfuse_session_id=body.get("langfuse_session_id"),
        langfuse_trace_id=body.get("langfuse_trace_id"),
        graph_enrich_enabled=True,
        timings_ms={},
        from_cache=False,
        abstained=False,
    )


def _telemetry_markdown(state: RAGState) -> str:
    timings = state.get("timings_ms") or {}
    parts = [f"{k}={v}" for k, v in sorted(timings.items())]
    return "rag_stage_ms " + " ".join(parts) + f" from_cache={state.get('from_cache', False)}"


async def stream_research_events(body: dict[str, Any]) -> AsyncIterator[str]:
    """Yield SSE `data:` lines per platform contract §7.9."""
    state = state_from_request(body)
    final = await run_rag_pipeline(state)
    answer = final.get("answer_text", "")

    # Token streaming stub — production: stream from vLLM chat completions
    if answer:
        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

    sources = final.get("sources") or []
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
    yield f"data: {json.dumps({'type': 'telemetry', 'markdown': _telemetry_markdown(final), 'timings_ms': final.get('timings_ms', {}), 'abstained': final.get('abstained', False), 'stub': final.get('stub', True)})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
