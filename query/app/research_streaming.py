"""SSE streaming for POST /research/stream — backed by LangGraph pipeline."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.models import AuthContext
from app.mcp_format import format_research_markdown
from app.rag_graph import run_rag_pipeline
from app.rag_state import RAGState
from app.session_store import SessionStore
from app.settings import get_settings


def state_from_request(
    body: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore | None = None,
) -> RAGState:
    settings = get_settings()
    tenant_id = body.get("tenant_id") or ctx.tenant_id
    session_id = body.get("session_id")
    history: list[dict[str, str]] = []
    if settings.sessions_enabled and session_id and session_store is not None:
        history = session_store.load_history(
            session_id,
            tenant_id=tenant_id,
            principal=ctx.principal,
            max_turns=settings.max_history_turns,
        )

    explicit = bool(body.get("document_id") or body.get("collection_id"))
    return RAGState(
        query=body.get("query", ""),
        tenant_id=tenant_id,
        collection_id=body.get("collection_id", ""),
        document_id=body.get("document_id"),
        version_id=body.get("version_id"),
        explicit_scope=explicit,
        skip_supervisor=explicit,
        request_id=body.get("request_id"),
        langfuse_session_id=body.get("langfuse_session_id") or session_id,
        langfuse_trace_id=body.get("langfuse_trace_id"),
        session_id=session_id,
        conversation_history=history,
        graph_enrich_enabled=True,
        timings_ms={},
        from_cache=False,
        abstained=False,
    )


def _telemetry_markdown(state: RAGState) -> str:
    return format_research_markdown(state).split("---\n", 1)[-1].strip()


async def stream_research_events(
    body: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore | None = None,
) -> AsyncIterator[str]:
    """Yield SSE ``data:`` lines per platform contract §7.9."""
    settings = get_settings()
    state = state_from_request(body, ctx=ctx, session_store=session_store)
    final = await run_rag_pipeline(state)
    answer = final.get("answer_text", "")

    if answer:
        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
            yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

    sources = final.get("sources") or []
    sources_md = "\n".join(
        f"{idx}. {s.get('label', s.get('title', 'source'))}"
        for idx, s in enumerate(sources, start=1)
    )
    yield f"data: {json.dumps({'type': 'sources', 'markdown': sources_md})}\n\n"
    yield f"data: {json.dumps({'type': 'telemetry', 'markdown': _telemetry_markdown(final), 'timings_ms': final.get('timings_ms', {}), 'abstained': final.get('abstained', False), 'stub': final.get('stub', True)})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

    session_id = body.get("session_id")
    if (
        settings.sessions_enabled
        and session_id
        and session_store is not None
        and final.get("answer_text")
    ):
        try:
            session_store.append_turn(
                session_id,
                tenant_id=state.get("tenant_id", ctx.tenant_id),
                principal=ctx.principal,
                user_content=body.get("query", ""),
                assistant_content=final.get("answer_text", ""),
                rag_metadata={"timings_ms": final.get("timings_ms") or {}},
            )
        except KeyError:
            pass
