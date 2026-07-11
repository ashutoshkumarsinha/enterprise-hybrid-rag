"""E-30 cross-collection query contract."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "docs" / "CROSS_COLLECTION_QUERIES.md"
SCHEMA = REPO_ROOT / "modules" / "schemas" / "mcp_research_documents.input.v1.json"
QDRANT = REPO_ROOT / "query" / "app" / "clients" / "qdrant.py"


def test_cross_collection_doc_exists() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "E-30" in text
    assert "additional_collection_ids" in text


def test_mcp_schema_allows_additional_collections() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    assert "additional_collection_ids" in props
    assert props["additional_collection_ids"]["type"] == "array"


def test_qdrant_client_supports_match_any_scope() -> None:
    text = QDRANT.read_text(encoding="utf-8")
    assert "additional_collection_ids" in text
    assert "MatchAny" in text
    assert "_scope_collection_ids" in text


def test_rag_state_includes_additional_collection_ids() -> None:
    text = (REPO_ROOT / "query" / "app" / "rag_state.py").read_text(encoding="utf-8")
    assert "additional_collection_ids" in text
