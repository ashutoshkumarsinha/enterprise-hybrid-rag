"""Supervisor query rewrite."""

from __future__ import annotations

import json
import os

from app.clients.chat import ChatClient
from app.supervisor import (
    build_supervisor_messages,
    parse_supervisor_response,
    stub_supervise,
    supervise_query,
)


def test_parse_supervisor_json() -> None:
    raw = json.dumps(
        {
            "rewritten_query": "API key rotation policy",
            "collection_id": "payments-api",
            "confidence": 0.9,
        }
    )
    parsed = parse_supervisor_response(raw, original_query="keys?")
    assert parsed["query"] == "API key rotation policy"
    assert parsed["collection_id"] == "payments-api"
    assert parsed["inference_score"] == 0.9


def test_stub_history_aware_rewrite() -> None:
    os.environ["HISTORY_AWARE_SUPERVISOR"] = "true"
    os.environ["CHAT_STUB"] = "true"
    state = {
        "query": "What about it?",
        "conversation_history": [
            {"role": "user", "content": "Tell me about refund policy"},
            {"role": "assistant", "content": "Refunds within 30 days."},
        ],
    }
    result = stub_supervise(state)
    assert "refund policy" in result["query"].lower()


def test_supervise_query_stub_passes_visual_intent() -> None:
    os.environ["CHAT_STUB"] = "true"
    os.environ["HISTORY_AWARE_SUPERVISOR"] = "false"
    client = ChatClient()
    result = supervise_query({"query": "Show the architecture diagram"}, client)
    assert result.get("visual_intent") is True


def test_build_supervisor_messages_includes_history() -> None:
    os.environ["HISTORY_AWARE_SUPERVISOR"] = "true"
    messages = build_supervisor_messages(
        {
            "query": "follow up",
            "tenant_id": "acme",
            "conversation_history": [{"role": "user", "content": "prior"}],
        }
    )
    roles = [m["role"] for m in messages]
    assert roles.count("user") >= 2
