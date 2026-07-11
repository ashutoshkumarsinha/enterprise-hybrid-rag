"""LangGraph RAG pipeline — cache → supervisor → embed → scope → retrieve → rerank → answer.

This module compiles the query-plane StateGraph described in
ENTERPRISE_HYBRID_RAG_SPEC.md §6.1. Each ``node_*`` function is one stage;
conditional edges handle cache hits and abstention without a separate router node.

Current status: **full pipeline wired** including supervisor LLM, circuit breakers, and degrade ladder.

Spec: §6.1 stage graph · FR-08 abstention · FR-09 timings_ms · FR-13 single embed.
"""

from __future__ import annotations

import os
import time
from typing import Literal

from langgraph.graph import END, StateGraph

from app.client_factory import (
    CircuitOpenError,
    complete_answer,
    embed_query,
    enrich_graph_blocks,
    get_reranker_client,
    rerank_chunks,
    retrieve_chunks,
    supervise_query,
)
from app.langsmith_config import setup_langsmith
from app.query_cache import get_cached_answer, set_cached_answer
from app.otel_metrics import record_rag_stage_ms
from app.rag_answer import answer_updates
from app.rag_state import RAGState
from app.telemetry import (
    SPAN_RAG_NODE_ANSWER,
    SPAN_RAG_NODE_CHECK_CACHE,
    SPAN_RAG_NODE_EMBED,
    SPAN_RAG_NODE_GRAPH,
    SPAN_RAG_NODE_RERANK,
    SPAN_RAG_NODE_RETRIEVE,
    SPAN_RAG_NODE_SCOPE,
    SPAN_RAG_NODE_SUPERVISOR,
    SPAN_RAG_PIPELINE,
    start_span,
    traced_rag_node,
)

# Compiled graph singleton — built once per process to avoid recompilation cost.
_COMPILED_GRAPH = None


def _tick(state: RAGState, stage: str, start: float) -> dict:
    """Record elapsed milliseconds for *stage* into ``timings_ms``.

    Every node should call this so FR-09 telemetry is consistent even in stubs.
    """
    timings = dict(state.get("timings_ms") or {})
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    timings[stage] = elapsed_ms
    record_rag_stage_ms(stage, elapsed_ms, tenant_id=state.get("tenant_id"))
    return {"timings_ms": timings}


@traced_rag_node(SPAN_RAG_NODE_CHECK_CACHE)
def node_check_cache(state: RAGState) -> dict:
    """Return a cached answer when Redis query cache hits (LG-3)."""
    start = time.perf_counter()
    cached = get_cached_answer(state)
    if cached:
        return {
            "from_cache": True,
            "answer_text": cached.get("answer_text", ""),
            "sources": cached.get("sources", []),
            "stub": cached.get("stub", False),
            **_tick(state, "cache_hit", start),
        }
    return {**_tick(state, "cache_hit", start), "from_cache": False}


@traced_rag_node(SPAN_RAG_NODE_SUPERVISOR)
def node_supervisor(state: RAGState) -> dict:
    """Optionally rewrite the user query before embedding (supervisor LLM).

    Reads: ``query``, ``skip_supervisor``, ``explicit_scope``, ``conversation_history``.
    Writes: ``query``, optional scope pins, ``scope_source``, ``timings_ms.supervisor``.

    Skipped when scope is explicit, supervisor disabled, or chat circuit is open.
    """
    start = time.perf_counter()
    updates = supervise_query(state)
    tick = _tick(state, "supervisor", start)
    if not updates:
        return tick
    merged = {**tick, **updates}
    if updates.get("collection_id") or updates.get("document_id"):
        merged.setdefault("scope_source", "inferred")
    return merged


@traced_rag_node(SPAN_RAG_NODE_EMBED)
def node_embed(state: RAGState) -> dict:
    """Embed the query once for dense + sparse retrieval (FR-13).

    Reads: ``query``.
    Writes: ``query_dense_vector``, ``query_sparse_vector``, ``timings_ms.embed``.
    """
    start = time.perf_counter()
    query = state.get("query", "")
    try:
        dense, sparse = embed_query(query)
    except CircuitOpenError:
        return {
            **_tick(state, "embed", start),
            "abstained": True,
            "degradation_level": "L3",
        }
    return {
        **_tick(state, "embed", start),
        "query_dense_vector": dense,
        "query_sparse_vector": sparse,
    }


@traced_rag_node(SPAN_RAG_NODE_SCOPE)
def node_scope(state: RAGState) -> dict:
    """Resolve which documents to search (explicit pins vs inferred scope).

    Reads: ``explicit_scope``, ``collection_id``, ``document_id``.
    Writes: ``scope_source`` (``explicit`` or ``inferred``), ``timings_ms.scope``.

    Full algorithm: ENTERPRISE_HYBRID_RAG_SPEC.md §6.7.
    """
    start = time.perf_counter()
    if state.get("scope_source"):
        source = state["scope_source"]
    else:
        source = "explicit" if state.get("explicit_scope") else "inferred"
    return {**_tick(state, "scope", start), "scope_source": source}


@traced_rag_node(SPAN_RAG_NODE_RETRIEVE)
def node_retrieve(state: RAGState) -> dict:
    """Hybrid dense + sparse retrieval from Qdrant with tenant filter (FR-02).

    Reads: ``tenant_id``, ``collection_id``, embed vectors.
    Writes: ``retrieved_chunks``, ``timings_ms.retrieve``.
    """
    start = time.perf_counter()
    if state.get("abstained"):
        return _tick(state, "retrieve", start)
    try:
        chunks = retrieve_chunks(state)
    except CircuitOpenError:
        return {
            **_tick(state, "retrieve", start),
            "abstained": True,
            "degradation_level": "L4",
            "retrieved_chunks": [],
        }
    return {**_tick(state, "retrieve", start), "retrieved_chunks": chunks}


@traced_rag_node(SPAN_RAG_NODE_RERANK)
def node_rerank(state: RAGState) -> dict:
    """Score retrieved chunks with the cross-encoder reranker; may abstain (FR-08).

    Reads: ``retrieved_chunks``.
    Writes: ``rerank_scores``, ``abstained``, ``timings_ms.rerank``.

    When ``abstained`` is True the graph routes directly to ``answer`` without LLM.
    Threshold: env ``MIN_RERANK_SCORE`` (production uses query.toml).
    """
    start = time.perf_counter()
    chunks = state.get("retrieved_chunks") or []
    query = state.get("query", "")
    degradation_level = state.get("degradation_level")
    try:
        ranked, scores = rerank_chunks(query, chunks)
    except CircuitOpenError:
        top_k = get_reranker_client().top_k
        ranked = sorted(chunks, key=lambda c: float(c.get("score", 0.0)), reverse=True)[:top_k]
        scores = [float(c.get("score", 0.0)) for c in ranked]
        degradation_level = degradation_level or "L2"
    min_score = float(os.environ.get("MIN_RERANK_SCORE", "0.0"))
    top_score = scores[0] if scores else 0.0
    abstained = top_score < min_score if scores else True
    updates = {
        **_tick(state, "rerank", start),
        "retrieved_chunks": ranked,
        "rerank_scores": scores,
        "abstained": abstained,
    }
    if degradation_level:
        updates["degradation_level"] = degradation_level
    return updates


@traced_rag_node(SPAN_RAG_NODE_GRAPH)
def node_graph_enrich(state: RAGState) -> dict:
    """Add Neo4j graph context (sections, cross-refs) to the LLM prompt.

    Reads: ``retrieved_chunks``, ``abstained``, ``graph_enrich_enabled``.
    Writes: ``context_blocks``, ``timings_ms.graph``.

    Skipped on abstention or when graph enrichment is disabled (degrade ladder L1).
    """
    start = time.perf_counter()
    if not state.get("graph_enrich_enabled", True) or state.get("abstained"):
        return _tick(state, "graph", start)
    try:
        blocks = enrich_graph_blocks(state)
    except CircuitOpenError:
        return {
            **_tick(state, "graph", start),
            "graph_enrich_enabled": False,
            "degradation_level": state.get("degradation_level") or "L1",
        }
    return {**_tick(state, "graph", start), "context_blocks": blocks}


@traced_rag_node(SPAN_RAG_NODE_ANSWER)
def node_answer(state: RAGState) -> dict:
    """Produce the final answer and sources (or abstention message).

    Reads: ``from_cache``, ``abstained``, ``query``, ``retrieved_chunks``, ``context_blocks``.
    Writes: ``answer_text``, ``sources``, ``timings_ms.answer``, ``stub``.

    Production streams tokens via vLLM; blocking path uses :func:`app.clients.chat.ChatClient`.
    """
    if state.get("from_cache"):
        return {}
    if state.get("abstained"):
        if state.get("degradation_level") in ("L3", "L4"):
            return answer_updates(
                state,
                "Temporarily unable to search. Please try again shortly.",
                stub=True,
            )
        return answer_updates(
            state,
            "I could not find enough relevant content to answer confidently.",
            stub=True,
        )
    try:
        text, is_stub = complete_answer(state)
    except CircuitOpenError:
        return answer_updates(
            state,
            "Temporarily unable to search. Please try again shortly.",
            stub=True,
        )
    updates = answer_updates(state, text, stub=is_stub)
    if not state.get("from_cache"):
        set_cached_answer(
            state,
            {
                "answer_text": updates["answer_text"],
                "sources": updates["sources"],
                "stub": updates.get("stub", is_stub),
            },
        )
    return updates


def _route_after_cache(state: RAGState) -> Literal["answer", "supervisor"]:
    """Branch: cache hit goes straight to answer; miss continues the pipeline."""
    if state.get("from_cache"):
        return "answer"
    return "supervisor"


def _route_after_rerank(state: RAGState) -> Literal["graph_enrich", "answer"]:
    """Branch: low rerank score abstains before graph enrich and LLM."""
    if state.get("abstained"):
        return "answer"
    return "graph_enrich"


def build_rag_graph():
    """Compile the RAG StateGraph (singleton via :func:`get_rag_graph`).

    Topology (spec §6.1): check_cache → supervisor → embed → scope → retrieve
    → rerank → graph_enrich → answer. Cache hits and abstention skip to answer.

    Side effect: registers LangSmith tracing when configured (TL-07).
    """
    setup_langsmith()

    graph = StateGraph(RAGState)
    graph.add_node("check_cache", node_check_cache)
    graph.add_node("supervisor", node_supervisor)
    graph.add_node("embed", node_embed)
    graph.add_node("scope", node_scope)
    graph.add_node("retrieve", node_retrieve)
    graph.add_node("rerank", node_rerank)
    graph.add_node("graph_enrich", node_graph_enrich)
    graph.add_node("answer", node_answer)

    graph.set_entry_point("check_cache")
    graph.add_conditional_edges("check_cache", _route_after_cache, {"answer": "answer", "supervisor": "supervisor"})
    graph.add_edge("supervisor", "embed")
    graph.add_edge("embed", "scope")
    graph.add_edge("scope", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_conditional_edges("rerank", _route_after_rerank, {"graph_enrich": "graph_enrich", "answer": "answer"})
    graph.add_edge("graph_enrich", "answer")
    graph.add_edge("answer", END)

    return graph.compile()


def get_rag_graph():
    """Return the compiled graph, building it on first use."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_rag_graph()
    return _COMPILED_GRAPH


async def run_rag_pipeline(initial: RAGState) -> RAGState:
    """Execute the full graph asynchronously and return the final state.

    Args:
        initial: Starting state — at minimum ``query``, ``tenant_id``, ``collection_id``.

    Returns:
        Merged state after the ``answer`` node, including ``answer_text`` and ``timings_ms``.
    """
    graph = get_rag_graph()
    with start_span(
        SPAN_RAG_PIPELINE,
        tenant_id=initial.get("tenant_id"),
        collection_id=initial.get("collection_id"),
        document_id=initial.get("document_id"),
    ):
        result = await graph.ainvoke(initial)
    return result  # type: ignore[return-value]
