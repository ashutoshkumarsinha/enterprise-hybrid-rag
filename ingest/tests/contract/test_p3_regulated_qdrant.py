"""E-33 regulated per-tenant Qdrant collection contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "docs" / "REGULATED_TENANT_QDRANT.md"
MIGRATION = REPO_ROOT / "ingest" / "migrations" / "005_tenant_qdrant_suffix_v1.sql"


def test_regulated_qdrant_doc_exists() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "E-33" in text
    assert "qdrant_collection_suffix" in text


def test_migration_adds_suffix_column() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "qdrant_collection_suffix" in sql


def test_resolve_qdrant_collection_helpers_match() -> None:
    from app.qdrant_collection import resolve_qdrant_collection

    assert resolve_qdrant_collection(tenant_id="acme", base="enterprise_hybrid_rag") == (
        "enterprise_hybrid_rag"
    )
    assert resolve_qdrant_collection(
        tenant_id="acme", base="enterprise_hybrid_rag", suffix="acme"
    ) == "enterprise_hybrid_rag_acme"


def test_query_resolver_exists() -> None:
    path = REPO_ROOT / "query" / "app" / "qdrant_collection.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "resolve_qdrant_collection" in text


def test_ingest_writer_uses_resolver() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "clients" / "qdrant.py").read_text(encoding="utf-8")
    assert "resolve_qdrant_collection" in text
