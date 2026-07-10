"""Chat client stub completions."""

from __future__ import annotations

import os

from app.clients.chat import ChatClient


def test_stub_complete() -> None:
    os.environ["CHAT_STUB"] = "true"
    client = ChatClient()
    state = {
        "query": "What is rate limiting?",
        "retrieved_chunks": [{"text": "Limit is 100 rpm", "collection_id": "api", "document_id": "ref"}],
    }
    text, is_stub = client.complete(state)
    assert is_stub
    assert "rate limiting" in text.lower()
