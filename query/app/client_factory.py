"""Circuit breaker registry and guarded client calls — E-28 · §18.15."""

from __future__ import annotations

import os
from typing import Any

from app.circuit_breaker import CircuitBreaker, CircuitOpenError, run_guarded
from app.clients.chat import ChatClient
from app.clients.embed import EmbedClient
from app.clients.neo4j import Neo4jClient
from app.clients.qdrant import QdrantClient, retrieve_for_state
from app.clients.reranker import RerankerClient

_embed: EmbedClient | None = None
_qdrant: QdrantClient | None = None
_chat: ChatClient | None = None
_reranker: RerankerClient | None = None
_neo4j: Neo4jClient | None = None
_breakers: dict[str, CircuitBreaker] | None = None


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw is not None else default


def get_breakers() -> dict[str, CircuitBreaker]:
    global _breakers
    if _breakers is None:
        _breakers = {
            "embed": CircuitBreaker(
                "embed",
                failure_threshold=_env_int("CIRCUIT_EMBED_FAILURES", 5),
                reset_timeout_s=_env_float("CIRCUIT_EMBED_RESET_S", 20.0),
            ),
            "chat": CircuitBreaker(
                "chat",
                failure_threshold=_env_int("CIRCUIT_CHAT_FAILURES", 5),
                reset_timeout_s=_env_float("CIRCUIT_CHAT_RESET_S", 30.0),
            ),
            "qdrant": CircuitBreaker(
                "qdrant",
                failure_threshold=_env_int("CIRCUIT_QDRANT_FAILURES", 3),
                reset_timeout_s=_env_float("CIRCUIT_QDRANT_RESET_S", 60.0),
            ),
            "neo4j": CircuitBreaker(
                "neo4j",
                failure_threshold=_env_int("CIRCUIT_NEO4J_FAILURES", 5),
                reset_timeout_s=_env_float("CIRCUIT_NEO4J_RESET_S", 30.0),
            ),
            "reranker": CircuitBreaker(
                "reranker",
                failure_threshold=_env_int("CIRCUIT_RERANKER_FAILURES", 5),
                reset_timeout_s=_env_float("CIRCUIT_RERANKER_RESET_S", 20.0),
            ),
        }
    return _breakers


def breaker_snapshots() -> dict[str, dict[str, object]]:
    return {name: breaker.snapshot() for name, breaker in get_breakers().items()}


def get_embed_client() -> EmbedClient:
    global _embed
    if _embed is None:
        _embed = EmbedClient()
    return _embed


def get_qdrant_client() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient()
    return _qdrant


def get_chat_client() -> ChatClient:
    global _chat
    if _chat is None:
        _chat = ChatClient()
    return _chat


def get_reranker_client() -> RerankerClient:
    global _reranker
    if _reranker is None:
        _reranker = RerankerClient()
    return _reranker


def get_neo4j_client() -> Neo4jClient:
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jClient()
    return _neo4j


def embed_query(text: str) -> tuple[list[float], dict[str, Any]]:
    client = get_embed_client()
    dense = run_guarded(get_breakers()["embed"], lambda: client.embed(text))
    sparse = client.sparse_from_text(text)
    return dense, sparse


def retrieve_chunks(state: dict[str, Any]) -> list[dict[str, Any]]:
    return run_guarded(
        get_breakers()["qdrant"],
        lambda: retrieve_for_state(state, get_embed_client(), get_qdrant_client()),
    )


def rerank_chunks(query: str, chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[float]]:
    client = get_reranker_client()
    return run_guarded(get_breakers()["reranker"], lambda: client.rerank(query, chunks))


def complete_answer(state: dict[str, Any]) -> tuple[str, bool]:
    client = get_chat_client()
    return run_guarded(get_breakers()["chat"], lambda: client.complete(state))


def enrich_graph_blocks(state: dict[str, Any]) -> list[str]:
    from app.graph_enrich import enrich_context_blocks

    return run_guarded(
        get_breakers()["neo4j"],
        lambda: enrich_context_blocks(state, get_neo4j_client()),
    )


def reset_clients() -> None:
    """Reset singletons — for tests."""
    global _embed, _qdrant, _chat, _reranker, _neo4j, _breakers
    _embed = None
    _qdrant = None
    _chat = None
    _reranker = None
    if _neo4j is not None:
        _neo4j.close()
    _neo4j = None
    _breakers = None


__all__ = [
    "CircuitOpenError",
    "breaker_snapshots",
    "complete_answer",
    "embed_query",
    "enrich_graph_blocks",
    "get_breakers",
    "get_chat_client",
    "get_embed_client",
    "get_neo4j_client",
    "get_qdrant_client",
    "get_reranker_client",
    "reset_clients",
    "rerank_chunks",
    "retrieve_chunks",
]
