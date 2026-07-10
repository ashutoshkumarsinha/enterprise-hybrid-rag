"""Startup warmup hook — FR-14.

Stub: logs intent until store/inference clients are wired (LG-1/LG-2).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def warmup_clients() -> None:
    """Preload clients for Qdrant, Neo4j, inference, and reranker."""
    logger.info("warmup_clients: stub — clients not yet pooled (see LG-1/LG-2)")
