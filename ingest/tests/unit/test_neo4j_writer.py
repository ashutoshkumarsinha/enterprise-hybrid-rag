"""Neo4j writer row mapping."""

from __future__ import annotations

import os

from app.clients.neo4j import Neo4jWriter, _chunk_row


def test_chunk_row_section_graph_id() -> None:
    row = _chunk_row(
        {
            "uuid": "00000000-0000-4000-8000-000000000001",
            "tenant_id": "acme",
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": "v1",
            "section_id": "security",
            "section_title": "Security",
            "text": "Rotate keys.",
            "type": "text",
        }
    )
    assert row["section_graph_id"] == "acme:docs:guide:security"


def test_stub_merge_returns_count() -> None:
    os.environ["NEO4J_STUB"] = "true"
    writer = Neo4jWriter()
    chunks = [
        {
            "uuid": "00000000-0000-4000-8000-000000000001",
            "tenant_id": "acme",
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": "v1",
            "text": "Rotate keys.",
            "type": "text",
        }
    ]
    merged = writer.merge_chunks(chunks)
    assert merged == 1
