"""Startup warmup hook — FR-14."""

from __future__ import annotations

import logging

from app.client_factory import get_embed_client, get_qdrant_client

logger = logging.getLogger(__name__)


def warmup_clients() -> None:
    """Preload and health-check Qdrant + embed clients."""
    qdrant = get_qdrant_client()
    embed = get_embed_client()
    q_ok = qdrant.healthcheck()
    e_ok = embed.healthcheck()
    logger.info(
        "warmup_clients: qdrant_ok=%s embed_ok=%s qdrant_stub=%s embed_stub=%s",
        q_ok,
        e_ok,
        qdrant.is_stub,
        embed.is_stub,
    )
