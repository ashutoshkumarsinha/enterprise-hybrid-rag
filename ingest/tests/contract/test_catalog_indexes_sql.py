"""INF-P2 catalog index DDL contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX_SQL = REPO_ROOT / "infra" / "scripts" / "postgres-catalog-indexes.sql"

REQUIRED_INDEXES = (
    "idx_acl_grants_principal",
    "idx_acl_grants_tenant_created",
    "idx_documents_tenant_collection_doc",
    "idx_document_versions_tenant",
    "idx_ingest_jobs_tenant_created",
    "idx_collections_tenant",
)


def test_catalog_indexes_sql_exists() -> None:
    assert INDEX_SQL.is_file()


def test_catalog_indexes_sql_declares_required_indexes() -> None:
    text = INDEX_SQL.read_text(encoding="utf-8")
    for name in REQUIRED_INDEXES:
        assert name in text, f"missing index {name}"
    assert "CREATE INDEX IF NOT EXISTS" in text
    assert "BEGIN;" in text and "COMMIT;" in text
