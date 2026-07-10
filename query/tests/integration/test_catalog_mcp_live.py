"""Catalog MCP tools against live or in-process HTTP."""

from __future__ import annotations


def test_list_indexed_documents_http(live_client) -> None:
    response = live_client.post(
        "/mcp/tools/list_indexed_documents",
        json={
            "tenant_id": "acme",
            "collection_id": "payments-api",
            "limit": 10,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "markdown" in body
    assert "count" in body
    assert isinstance(body["count"], int)


def test_get_document_metadata_not_found_live(live_client) -> None:
    response = live_client.post(
        "/mcp/tools/get_document_metadata",
        json={
            "tenant_id": "acme",
            "document_id": "definitely-missing-doc-id",
            "collection_id": "payments-api",
        },
    )
    assert response.status_code == 404


def test_visualize_document_graph_not_found_live(live_client) -> None:
    response = live_client.post(
        "/mcp/tools/visualize_document_graph",
        json={
            "tenant_id": "acme",
            "document_id": "definitely-missing-doc-id",
            "collection_id": "payments-api",
        },
    )
    assert response.status_code == 404
