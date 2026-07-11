"""Qdrant writer stub mode."""

from __future__ import annotations

import os

from app.clients.embed import EmbedClient
from app.clients.qdrant import QdrantWriter


def test_stub_upsert_returns_count() -> None:
    os.environ["QDRANT_STUB"] = "true"
    writer = QdrantWriter()
    embed = EmbedClient(dimension=8)
    chunks = [
        {
            "uuid": "00000000-0000-4000-8000-000000000001",
            "tenant_id": "acme",
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": "v1",
            "title": "Guide",
            "text": "Rotate API keys monthly.",
            "type": "text",
            "ingested_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    dense = [embed.embed(chunks[0]["text"])]
    sparse = [embed.sparse_from_text(chunks[0]["text"])]
    written = writer.upsert_chunks(chunks, dense_vectors=dense, sparse_vectors=sparse)
    assert written == 1
    assert writer.is_stub is True
