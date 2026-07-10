"""Pooled store/inference clients — FR-14 warmup entry point."""

from __future__ import annotations

from app.clients.embed import EmbedClient
from app.clients.qdrant import QdrantClient

_embed: EmbedClient | None = None
_qdrant: QdrantClient | None = None


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


def reset_clients() -> None:
    """Reset singletons — for tests."""
    global _embed, _qdrant
    _embed = None
    _qdrant = None
