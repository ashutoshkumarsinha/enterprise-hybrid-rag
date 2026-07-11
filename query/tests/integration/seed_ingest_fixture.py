"""Seed ingest-shaped corpus into Qdrant for query integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.clients.embed import EmbedClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_FIXTURE = _REPO_ROOT / "ingest" / "tests" / "fixtures" / "chunks" / "e2e-api-keys.json"


def load_ingest_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or _DEFAULT_FIXTURE
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def upsert_ingest_fixture(fixture: dict[str, Any]) -> None:
    """Upsert fixture chunks using the same vector layout as hybrid-rag-ingest."""
    from qdrant_client import QdrantClient, models

    import os

    embed = EmbedClient()
    url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
    collection = os.environ.get("QDRANT_COLLECTION", "enterprise_hybrid_rag")
    client = QdrantClient(url=url)
    chunks = fixture["chunks"]
    texts = [chunk["text"] for chunk in chunks]
    dense_vectors = embed.embed_batch(texts)
    points = []
    for chunk, dense in zip(chunks, dense_vectors, strict=True):
        sparse = embed.sparse_from_text(chunk["text"])
        points.append(
            models.PointStruct(
                id=chunk["uuid"],
                vector={
                    "": dense,
                    "bm25-text": models.SparseVector(
                        indices=sparse["indices"],
                        values=sparse["values"],
                    ),
                },
                payload=chunk,
            )
        )
    client.upsert(collection_name=collection, points=points, wait=True)
