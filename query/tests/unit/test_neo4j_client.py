"""Neo4j client stub enrichment."""

from __future__ import annotations

import os

from app.client_factory import reset_clients
from app.clients.neo4j import Neo4jClient


def test_stub_enrich_returns_lineage_and_refs() -> None:
    reset_clients()
    os.environ["NEO4J_STUB"] = "true"
    client = Neo4jClient()
    chunks = [
        {
            "uuid": "00000000-0000-4000-8000-000000000001",
            "tenant_id": "acme",
            "collection_id": "docs",
            "document_id": "guide",
            "section_title": "Security",
            "text": "Rotate keys.",
            "references": ["refund-policy"],
        }
    ]
    meta = client.enrich_chunks(chunks, tenant_id="acme")
    assert "00000000-0000-4000-8000-000000000001" in meta
    entry = meta["00000000-0000-4000-8000-000000000001"]
    assert entry["lineage"]
    assert "refund-policy" in entry["cross_refs"]
    assert entry["stub"] is True


def test_healthcheck_stub_mode() -> None:
    os.environ["NEO4J_STUB"] = "true"
    client = Neo4jClient()
    assert client.healthcheck() is True
