"""SSE streaming for POST /research/stream — backed by LangGraph pipeline."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from app.client_factory import get_chat_client
from app.models import AuthContext
from app.mcp_format import format_research_markdown
from app.query_cache import set_cached_answer
from app.rag_answer import answer_updates
from app.rag_graph import node_answer
from app.rag_runner import advance_to_answer
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


def _merge_state(state: RAGState, updates: dict[str, Any]) -> RAGState:
    merged = dict(state)
    merged.update(updates)
    return merged  # type: ignore[return-value]


async def _yield_answer_tokens(answer: str) -> AsyncIterator[str]:
    if not answer:
        return
    words = answer.split(" ")
    for i, word in enumerate(words):
        chunk = word if i == 0 else f" {word}"
        yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"


async def stream_research_events(
    body: dict[str, Any],
    *,
    ctx: AuthContext,
    session_store: SessionStore | None = None,
) -> AsyncIterator[str]:
    """Yield SSE ``data:`` lines per platform contract §7.9."""
    settings = get_settings()
    state = state_from_request(body, ctx=ctx, session_store=session_store)
    preflight = advance_to_answer(state)

    if preflight.get("from_cache"):
        final = preflight
        async for event in _yield_answer_tokens(final.get("answer_text", "")):
            yield event
    elif preflight.get("abstained"):
        final = _merge_state(preflight, node_answer(preflight))
        async for event in _yield_answer_tokens(final.get("answer_text", "")):
            yield event
    else:
        chat = get_chat_client()
        parts: list[str] = []
        stream_start = time.perf_counter()
        async for token in chat.stream_tokens(preflight):
            parts.append(token)
            yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
        timings = dict(preflight.get("timings_ms") or {})
        timings["answer"] = int((time.perf_counter() - stream_start) * 1000)
        preflight = _merge_state(preflight, {"timings_ms": timings})
        final = _merge_state(
            preflight,
            answer_updates(preflight, "".join(parts), stub=chat.is_stub),
        )
        set_cached_answer(
            state,
            {
                "answer_text": final.get("answer_text", ""),
                "sources": final.get("sources", []),
                "stub": final.get("stub", chat.is_stub),
            },
        )

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
