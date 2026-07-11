"""Orchestrate embed + store writes for ingest batches."""

from __future__ import annotations

import os
from typing import Any

from app.clients.embed import EmbedClient
from app.clients.neo4j import Neo4jWriter
from app.clients.qdrant import QdrantWriter
from app.telemetry import get_tracer

_DEFAULT_BATCH_SIZE = 32


def _batch_size() -> int:
    return int(os.environ.get("INGEST_BATCH_SIZE", os.environ.get("BATCH_SIZE", str(_DEFAULT_BATCH_SIZE))))


def _write_stub_enabled() -> bool:
    return os.environ.get("INGEST_WRITE_STUB", "true").lower() in ("true", "1", "yes")


def write_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate, embed, and upsert chunk payloads to Qdrant + Neo4j."""
    tracer = get_tracer()
    validated = [chunk for chunk in chunks if chunk.get("uuid") and chunk.get("text")]
    if not validated:
        return {"written": 0, "validated": 0, "stub": True}

    if _write_stub_enabled():
        return {"written": 0, "validated": len(validated), "stub": True}

    embed_client = EmbedClient()
    qdrant = QdrantWriter()
    neo4j = Neo4jWriter()
    dense_vectors: list[list[float]] = []
    sparse_vectors: list[dict[str, Any]] = []

    with tracer.start_as_current_span("inference/embed/batch") as span:
        span.set_attribute("ingest.chunk_count", len(validated))
        texts = [chunk["text"] for chunk in validated]
        for start in range(0, len(texts), _batch_size()):
            batch_texts = texts[start : start + _batch_size()]
            dense_vectors.extend(embed_client.embed_batch(batch_texts))
        for text in texts:
            sparse_vectors.append(embed_client.sparse_from_text(text))

    with tracer.start_as_current_span("store/qdrant/upsert") as span:
        span.set_attribute("ingest.chunk_count", len(validated))
        qdrant_written = qdrant.upsert_chunks(
            validated,
            dense_vectors=dense_vectors,
            sparse_vectors=sparse_vectors,
        )
        span.set_attribute("ingest.qdrant_written", qdrant_written)

    with tracer.start_as_current_span("store/neo4j/merge") as span:
        span.set_attribute("ingest.chunk_count", len(validated))
        neo4j_written = neo4j.merge_chunks(validated)
        span.set_attribute("ingest.neo4j_written", neo4j_written)
    neo4j.close()

    return {
        "written": qdrant_written,
        "validated": len(validated),
        "qdrant_written": qdrant_written,
        "neo4j_written": neo4j_written,
        "stub": embed_client.is_stub and qdrant.is_stub and neo4j.is_stub,
    }
