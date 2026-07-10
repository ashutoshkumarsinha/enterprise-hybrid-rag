"""Catalog store ACL filtering and formatting."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.acl import can_read_document
from app.catalog_handlers import (
    handle_get_document_metadata,
    handle_list_indexed_documents,
)
from app.catalog_store import InMemoryCatalogStore, format_documents_markdown
from app.models import AuthContext


def test_open_collection_lists_documents() -> None:
    store = InMemoryCatalogStore()
    docs, _ = store.list_indexed_documents(
        tenant_id="acme",
        principal="user:bob",
        collection_id="payments-api",
    )
    assert len(docs) == 2
    markdown = format_documents_markdown(docs)
    assert "admin-guide" in markdown
    assert "refund-policy" in markdown


def test_secured_collection_empty_for_unauthorized_principal() -> None:
    store = InMemoryCatalogStore()
    docs, _ = store.list_indexed_documents(
        tenant_id="acme",
        principal="user:bob",
        collection_id="internal-only",
    )
    assert docs == []


def test_secured_collection_visible_for_granted_principal() -> None:
    store = InMemoryCatalogStore()
    docs, _ = store.list_indexed_documents(
        tenant_id="acme",
        principal="user:alice",
        collection_id="internal-only",
    )
    assert len(docs) == 1
    assert docs[0]["document_id"] == "payroll"


def test_acl_helper_default_acl_allows() -> None:
    assert can_read_document(
        {"user:alice"},
        collection_id="internal-only",
        document_id="payroll",
        default_acl=["user:alice"],
        grants=[],
    )


def test_get_document_metadata_not_found() -> None:
    store = InMemoryCatalogStore()
    ctx = AuthContext("acme", "user:bob", ["mcp.catalog.read"], "mcp_token")
    with pytest.raises(HTTPException) as exc:
        handle_get_document_metadata(
            {"document_id": "missing"},
            ctx=ctx,
            catalog_store=store,
        )
    assert exc.value.status_code == 404


def test_list_handler_returns_markdown() -> None:
    store = InMemoryCatalogStore()
    ctx = AuthContext("acme", "user:bob", ["mcp.catalog.read"], "mcp_token")
    result = handle_list_indexed_documents(
        {"collection_id": "payments-api"},
        ctx=ctx,
        catalog_store=store,
    )
    assert result["count"] == 2
    assert "admin-guide" in result["markdown"]
