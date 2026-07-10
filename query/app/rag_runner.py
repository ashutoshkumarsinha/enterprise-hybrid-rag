"""Pipeline preflight — run stages before streaming answer tokens."""

from __future__ import annotations

from typing import Any

from app.rag_graph import (
    node_check_cache,
    node_embed,
    node_graph_enrich,
    node_rerank,
    node_retrieve,
    node_scope,
    node_supervisor,
)
from app.rag_state import RAGState


def _merge(state: RAGState, updates: dict[str, Any]) -> RAGState:
    merged = dict(state)
    merged.update(updates)
    return merged  # type: ignore[return-value]


def advance_to_answer(state: RAGState) -> RAGState:
    """Run graph stages through graph_enrich (or stop on cache/abstain)."""
    s = _merge(state, node_check_cache(state))
    if s.get("from_cache"):
        return s
    for fn in (node_supervisor, node_embed, node_scope, node_retrieve, node_rerank):
        s = _merge(s, fn(s))
    if s.get("abstained"):
        return s
    return _merge(s, node_graph_enrich(s))
