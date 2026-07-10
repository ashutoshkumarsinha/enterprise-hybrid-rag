"""Supervisor node integration."""

from __future__ import annotations

import os

from app.client_factory import reset_clients
from app.rag_graph import node_supervisor
from app.rag_state import RAGState


def test_supervisor_skipped_when_explicit_scope() -> None:
    os.environ["CHAT_STUB"] = "true"
    os.environ["SUPERVISOR_ENABLED"] = "true"
    reset_clients()
    state = RAGState(
        query="keys?",
        explicit_scope=True,
        skip_supervisor=True,
        timings_ms={},
    )
    result = node_supervisor(state)
    assert "query" not in result or result.get("query") is None


def test_supervisor_rewrites_with_history() -> None:
    os.environ["CHAT_STUB"] = "true"
    os.environ["SUPERVISOR_ENABLED"] = "true"
    os.environ["HISTORY_AWARE_SUPERVISOR"] = "true"
    reset_clients()
    state = RAGState(
        query="What about it?",
        conversation_history=[{"role": "user", "content": "Refund windows"}],
        timings_ms={},
    )
    result = node_supervisor(state)
    assert "Refund" in result.get("query", "")
