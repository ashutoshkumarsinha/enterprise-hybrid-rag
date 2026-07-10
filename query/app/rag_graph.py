"""LangGraph RAG pipeline — cache → supervisor → embed → scope → retrieve → rerank → answer.

This module compiles the query-plane StateGraph described in
ENTERPRISE_HYBRID_RAG_SPEC.md §6.1. Each ``node_*`` function is one stage;
conditional edges handle cache hits and abstention without a separate router node.

Current status: **embed + Qdrant retrieve wired** via ``app/clients/``; answer/LLM and
reranker HTTP remain stub until LG-2/LG-3.

Spec: §6.1 stage graph · FR-08 abstention · FR-09 timings_ms · FR-13 single embed.
"""

from __future__ import annotations

import os
import time
from typing import Literal

from langgraph.graph import END, StateGraph

from app.client_factory import get_embed_client, get_qdrant_client
from app.clients.qdrant import retrieve_for_state
from app.langsmith_config import setup_langsmith
from app.rag_state import RAGState

# Compiled graph singleton — built once per process to avoid recompilation cost.
_COMPILED_GRAPH = None


def _tick(state: RAGState, stage: str, start: float) -> dict:
    """Record elapsed milliseconds for *stage* into ``timings_ms``.

    Every node should call this so FR-09 telemetry is consistent even in stubs.
    """
    timings = dict(state.get("timings_ms") or {})
    timings[stage] = int((time.perf_counter() - start) * 1000)
    return {"timings_ms": timings}


def node_check_cache(state: RAGState) -> dict:
    """Return a cached answer when Redis query cache hits.

    Reads: ``request_id``, existing ``timings_ms``.
    Writes: ``from_cache``, optional ``answer_text`` / ``sources``, ``timings_ms.cache_hit``.

    Stub: real lookup lives in ``query_cache.py`` (not yet implemented).
    Controlled by env ``QUERY_CACHE_ENABLED`` for local experiments only.
    """
    start = time.perf_counter()
    enabled = os.environ.get("QUERY_CACHE_ENABLED", "").lower() in ("true", "1", "yes")
    if enabled and state.get("request_id", "").endswith("cached"):
        return {
            "from_cache": True,
            "answer_text": "Cached stub answer",
            "sources": [],
            **_tick(state, "cache_hit", start),
        }
    return {**_tick(state, "cache_hit", start), "from_cache": False}


def node_supervisor(state: RAGState) -> dict:
    """Optionally rewrite the user query before embedding (supervisor LLM).

    Reads: ``query``, ``skip_supervisor``, ``explicit_scope``.
    Writes: ``timings_ms.supervisor`` (query text unchanged in stub).

    Skipped when the client sent explicit scope pins or ``skip_supervisor`` is set.
    """
    start = time.perf_counter()
    if state.get("skip_supervisor") or state.get("explicit_scope"):
        return _tick(state, "supervisor", start)
    # Stub: optional LLM rewrite — pass through query until inference client exists.
    return _tick(state, "supervisor", start)


def node_embed(state: RAGState) -> dict:
    """Embed the query once for dense + sparse retrieval (FR-13).

    Reads: ``query``.
    Writes: ``query_dense_vector``, ``query_sparse_vector``, ``timings_ms.embed``.
    """
    start = time.perf_counter()
    embed = get_embed_client()
    query = state.get("query", "")
    dense = embed.embed(query)
    sparse = embed.sparse_from_text(query)
    return {
        **_tick(state, "embed", start),
        "query_dense_vector": dense,
        "query_sparse_vector": sparse,
    }


def node_scope(state: RAGState) -> dict:
    """Resolve which documents to search (explicit pins vs inferred scope).

    Reads: ``explicit_scope``, ``collection_id``, ``document_id``.
    Writes: ``scope_source`` (``explicit`` or ``inferred``), ``timings_ms.scope``.

    Full algorithm: ENTERPRISE_HYBRID_RAG_SPEC.md §6.7.
    """
    start = time.perf_counter()
    source = "explicit" if state.get("explicit_scope") else "inferred"
    return {**_tick(state, "scope", start), "scope_source": source}


def node_retrieve(state: RAGState) -> dict:
    """Hybrid dense + sparse retrieval from Qdrant with tenant filter (FR-02).

    Reads: ``tenant_id``, ``collection_id``, embed vectors.
    Writes: ``retrieved_chunks``, ``timings_ms.retrieve``.
    """
    start = time.perf_counter()
    chunks = retrieve_for_state(state, get_embed_client(), get_qdrant_client())
    return {**_tick(state, "retrieve", start), "retrieved_chunks": chunks}


def node_rerank(state: RAGState) -> dict:
    """Score retrieved chunks with the cross-encoder reranker; may abstain (FR-08).

    Reads: ``retrieved_chunks``.
    Writes: ``rerank_scores``, ``abstained``, ``timings_ms.rerank``.

    When ``abstained`` is True the graph routes directly to ``answer`` without LLM.
    Threshold: env ``MIN_RERANK_SCORE`` (production uses query.toml).
    """
    start = time.perf_counter()
    chunks = state.get("retrieved_chunks") or []
    scores = [float(c.get("score", 0.85)) for c in chunks] or [0.0]
    min_score = float(os.environ.get("MIN_RERANK_SCORE", "0.0"))
    abstained = scores[0] < min_score if scores else True
    return {
        **_tick(state, "rerank", start),
        "rerank_scores": scores,
        "abstained": abstained,
    }


def node_graph_enrich(state: RAGState) -> dict:
    """Add Neo4j graph context (sections, cross-refs) to the LLM prompt.

    Reads: ``retrieved_chunks``, ``abstained``, ``graph_enrich_enabled``.
    Writes: ``context_blocks``, ``timings_ms.graph``.

    Skipped on abstention or when graph enrichment is disabled (degrade ladder L1).
    """
    start = time.perf_counter()
    if not state.get("graph_enrich_enabled", True) or state.get("abstained"):
        return _tick(state, "graph", start)
    blocks = [c.get("text", "") for c in state.get("retrieved_chunks") or []]
    return {**_tick(state, "graph", start), "context_blocks": blocks}


def node_answer(state: RAGState) -> dict:
    """Produce the final answer and sources (or abstention message).

    Reads: ``from_cache``, ``abstained``, ``query``, ``retrieved_chunks``, ``context_blocks``.
    Writes: ``answer_text``, ``sources``, ``timings_ms.answer``, ``stub``.

    Production streams tokens via vLLM; this stub returns a single string for tests.
    """
    start = time.perf_counter()
    if state.get("from_cache"):
        return _tick(state, "answer", start)
    if state.get("abstained"):
        text = "I could not find enough relevant content to answer confidently."
        return {
            **_tick(state, "answer", start),
            "answer_text": text,
            "sources": [],
            "stub": True,
        }
    query = state.get("query", "")
    qdrant = get_qdrant_client()
    embed = get_embed_client()
    using_stub = qdrant.is_stub or embed.is_stub
    text = f"Stub grounded answer for: {query[:200]}"
    sources = []
    for chunk in state.get("retrieved_chunks") or []:
        sources.append(
            {
                "label": chunk.get("label")
                or f"{chunk.get('collection_id', '')} / {chunk.get('document_id', '')}",
                "document_id": chunk.get("document_id"),
                "collection_id": chunk.get("collection_id"),
                "score": chunk.get("score"),
            }
        )
    return {
        **_tick(state, "answer", start),
        "answer_text": text,
        "sources": sources,
        "stub": using_stub,
    }


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
    result = await graph.ainvoke(initial)
    return result  # type: ignore[return-value]
