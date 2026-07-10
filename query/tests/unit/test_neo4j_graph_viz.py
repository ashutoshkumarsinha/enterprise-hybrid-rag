"""Neo4j document graph Mermaid output."""

from __future__ import annotations

import os

from app.clients.neo4j import Neo4jClient


def test_stub_document_graph_mermaid() -> None:
    os.environ["NEO4J_STUB"] = "true"
    client = Neo4jClient()
    mermaid = client.document_graph_mermaid(
        tenant_id="acme",
        collection_id="payments-api",
        document_id="admin-guide",
    )
    assert "flowchart TB" in mermaid
    assert "admin-guide" in mermaid
