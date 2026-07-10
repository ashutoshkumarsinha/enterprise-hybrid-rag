"""Reranker client ordering."""

from __future__ import annotations

import os

from app.clients.reranker import RerankerClient


def test_stub_rerank_orders_by_score() -> None:
    os.environ["RERANKER_STUB"] = "true"
    client = RerankerClient(top_k=2)
    chunks = [
        {"text": "low", "score": 0.2, "document_id": "a"},
        {"text": "high", "score": 0.9, "document_id": "b"},
        {"text": "mid", "score": 0.5, "document_id": "c"},
    ]
    ranked, scores = client.rerank("query", chunks)
    assert len(ranked) == 2
    assert ranked[0]["document_id"] == "b"
    assert scores[0] == 0.9
