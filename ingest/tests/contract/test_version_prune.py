"""E-22 version retention SQL contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_STORE = REPO_ROOT / "ingest" / "app" / "catalog_store.py"


def test_catalog_store_prune_query_uses_row_number_and_latest_guard() -> None:
    text = CATALOG_STORE.read_text(encoding="utf-8")
    assert "list_prunable_versions" in text
    assert "ROW_NUMBER() OVER" in text
    assert "version_id <> latest_version_id" in text
    assert "delete_versions" in text
