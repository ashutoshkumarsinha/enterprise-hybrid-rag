"""Qdrant client stub mode and chunk mapping."""

from __future__ import annotations

import os

from app.client_factory import reset_clients
from app.clients.qdrant import QdrantClient, _point_to_chunk


def test_stub_hybrid_search_returns_chunk() -> None:
    reset_clients()
    os.environ["QDRANT_STUB"] = "true"
    client = QdrantClient()
    chunks = client.hybrid_search(
        tenant_id="acme",
        dense_vector=[0.1] * 8,
        sparse_indices=[1, 2],
        sparse_values=[1.0, 1.0],
        collection_id="docs",
        document_id="guide",
    )
    assert len(chunks) == 1
    assert chunks[0]["tenant_id"] == "acme"
    assert chunks[0]["document_id"] == "guide"


def test_point_to_chunk_label() -> None:
    class Point:
        id = "1"
        score = 0.9
        payload = {
            "collection_id": "payments-api",
            "document_id": "admin-guide",
            "section_title": "Security",
            "text": "Rotate keys monthly.",
            "tenant_id": "acme",
        }

    chunk = _point_to_chunk(Point())
    assert "payments-api" in chunk["label"]
    assert chunk["score"] == 0.9
