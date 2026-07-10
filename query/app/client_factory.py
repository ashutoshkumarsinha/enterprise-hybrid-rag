"""Pooled store/inference clients — FR-14 warmup entry point."""

from __future__ import annotations

from app.clients.chat import ChatClient
from app.clients.embed import EmbedClient
from app.clients.qdrant import QdrantClient
from app.clients.reranker import RerankerClient

_embed: EmbedClient | None = None
_qdrant: QdrantClient | None = None
_chat: ChatClient | None = None
_reranker: RerankerClient | None = None


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


def reset_clients() -> None:
    """Reset singletons — for tests."""
    global _embed, _qdrant, _chat, _reranker
    _embed = None
    _qdrant = None
    _chat = None
    _reranker = None
