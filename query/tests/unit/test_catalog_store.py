"""Catalog store ACL filtering and formatting."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.acl import can_read_document
from app.acl_cache import flush_acl_cache, get_acl_entry
from app.catalog_handlers import (
    handle_get_document_metadata,
    handle_list_indexed_documents,
)
from app.catalog_store import InMemoryCatalogStore, PostgresCatalogStore, format_documents_markdown
from app.models import AuthContext


@pytest.fixture(autouse=True)
def _reset_acl_cache() -> None:
    flush_acl_cache()


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


def test_postgres_load_acl_uses_cache() -> None:
    class _Cursor:
        def __init__(self) -> None:
            self.execute_count = 0
            self._sql = ""

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, sql: str, params: object = None) -> None:
            self.execute_count += 1
            self._sql = sql

        def fetchall(self) -> list:
            if "collections" in self._sql:
                return [("payments-api", ["user:alice"])]
            return []

    class _Conn:
        def __init__(self) -> None:
            self.cursor_obj = _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self) -> _Cursor:
            return self.cursor_obj

    store = PostgresCatalogStore("postgresql://stub")
    conn = _Conn()
    first = store._load_acl(conn, tenant_id="acme", principal="user:alice")
    second = store._load_acl(conn, tenant_id="acme", principal="user:alice")
    assert first[0] == second[0]
    assert conn.cursor_obj.execute_count == 2
    assert get_acl_entry(tenant_id="acme", principal="user:alice") is not None
    flush_acl_cache("acme")
    store._load_acl(conn, tenant_id="acme", principal="user:alice")
    assert conn.cursor_obj.execute_count == 4
