"""Preflight runner smoke test."""

from __future__ import annotations

import os

from app.client_factory import reset_clients
from app.rag_runner import advance_to_answer
from app.rag_state import RAGState


def test_advance_to_answer_populates_chunks() -> None:
    os.environ["QDRANT_STUB"] = "true"
    os.environ["EMBED_STUB"] = "true"
    os.environ["RERANKER_STUB"] = "true"
    reset_clients()
    state = RAGState(
        query="test query",
        tenant_id="dev",
        collection_id="docs",
        explicit_scope=True,
        skip_supervisor=True,
        graph_enrich_enabled=True,
        timings_ms={},
        from_cache=False,
        abstained=False,
    )
    result = advance_to_answer(state)
    assert result.get("retrieved_chunks")
    assert result.get("context_blocks") is not None or not result.get("abstained")
