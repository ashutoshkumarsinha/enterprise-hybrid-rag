"""Startup warmup hook — FR-14."""

from __future__ import annotations

import logging

from app.client_factory import (
    get_chat_client,
    get_embed_client,
    get_qdrant_client,
    get_reranker_client,
)

logger = logging.getLogger(__name__)


def warmup_clients() -> None:
    """Preload and health-check store + inference clients."""
    qdrant = get_qdrant_client()
    embed = get_embed_client()
    chat = get_chat_client()
    reranker = get_reranker_client()
    logger.info(
        "warmup_clients: qdrant=%s embed=%s chat=%s reranker=%s",
        qdrant.healthcheck(),
        embed.healthcheck(),
        chat.healthcheck(),
        reranker.healthcheck(),
    )
