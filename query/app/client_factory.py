"""Pooled store/inference clients — FR-14 warmup entry point."""

from __future__ import annotations

from app.clients.chat import ChatClient
from app.clients.embed import EmbedClient
from app.clients.neo4j import Neo4jClient
from app.clients.qdrant import QdrantClient
from app.clients.reranker import RerankerClient

_embed: EmbedClient | None = None
_qdrant: QdrantClient | None = None
_chat: ChatClient | None = None
_reranker: RerankerClient | None = None
_neo4j: Neo4jClient | None = None


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


def reset_clients() -> None:
    """Reset singletons — for tests."""
    global _embed, _qdrant, _chat, _reranker, _neo4j
    _embed = None
    _qdrant = None
    _chat = None
    _reranker = None
    if _neo4j is not None:
        _neo4j.close()
    _neo4j = None
