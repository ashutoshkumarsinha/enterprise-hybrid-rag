"""Supervisor node with live inference backends."""

from __future__ import annotations

import os

from app.rag_graph import node_supervisor
from app.rag_state import RAGState


def test_supervisor_live_runs() -> None:
    state = RAGState(
        query="What is the API key rotation policy?",
        tenant_id=os.environ.get("DEFAULT_TENANT_ID", "dev"),
        collection_id=os.environ.get("LIVE_TEST_COLLECTION_ID", ""),
        explicit_scope=False,
        skip_supervisor=False,
        conversation_history=[],
        timings_ms={},
    )
    result = node_supervisor(state)
    timings = result.get("timings_ms") or {}
    assert "supervisor" in timings
    assert result.get("query")


def test_supervisor_history_aware_live(monkeypatch) -> None:
    monkeypatch.setenv("HISTORY_AWARE_SUPERVISOR", "true")
    from app.settings import get_settings

    get_settings.cache_clear()
    state = RAGState(
        query="Can you elaborate on that?",
        tenant_id=os.environ.get("DEFAULT_TENANT_ID", "dev"),
        explicit_scope=False,
        skip_supervisor=False,
        conversation_history=[
            {"role": "user", "content": "Explain refund policy"},
            {"role": "assistant", "content": "Refunds within 30 days."},
        ],
        timings_ms={},
    )
    result = node_supervisor(state)
    assert result.get("query")
    get_settings.cache_clear()
