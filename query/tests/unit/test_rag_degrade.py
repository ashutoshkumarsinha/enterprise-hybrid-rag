"""RAG degrade paths when breakers are open."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.circuit_breaker import CircuitOpenError
from app.client_factory import reset_clients
from app.rag_graph import node_embed, node_rerank, node_retrieve
from app.rag_state import RAGState


@pytest.fixture(autouse=True)
def _stub_env() -> None:
    os.environ["CIRCUIT_BREAKERS_ENABLED"] = "true"
    os.environ["QDRANT_STUB"] = "true"
    os.environ["EMBED_STUB"] = "true"
    os.environ["RERANKER_STUB"] = "true"
    os.environ["NEO4J_STUB"] = "true"
    reset_clients()
    yield
    reset_clients()


def test_embed_breaker_open_abstains_l3() -> None:
    state = RAGState(query="hello", timings_ms={})
    with patch("app.rag_graph.embed_query", side_effect=CircuitOpenError("embed")):
        result = node_embed(state)
    assert result["abstained"] is True
    assert result["degradation_level"] == "L3"


def test_qdrant_breaker_open_abstains_l4() -> None:
    state = RAGState(
        query="hello",
        tenant_id="dev",
        query_dense_vector=[0.1],
        query_sparse_vector={"indices": [1], "values": [1.0]},
        timings_ms={},
    )
    with patch("app.rag_graph.retrieve_chunks", side_effect=CircuitOpenError("qdrant")):
        result = node_retrieve(state)
    assert result["abstained"] is True
    assert result["degradation_level"] == "L4"


def test_reranker_breaker_uses_dense_top_k_l2() -> None:
    state = RAGState(
        query="hello",
        retrieved_chunks=[
            {"text": "low", "score": 0.2},
            {"text": "high", "score": 0.9},
        ],
        timings_ms={},
    )
    with patch("app.rag_graph.rerank_chunks", side_effect=CircuitOpenError("reranker")):
        result = node_rerank(state)
    assert result["degradation_level"] == "L2"
    assert result["retrieved_chunks"][0]["text"] == "high"
