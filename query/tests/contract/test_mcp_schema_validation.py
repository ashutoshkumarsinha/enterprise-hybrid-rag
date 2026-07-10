"""Validate MCP JSON schemas against modules/schemas."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = REPO_ROOT / "modules" / "schemas"


@pytest.mark.parametrize(
    "schema_name,sample",
    [
        (
            "mcp_research_documents.input.v1.json",
            {"query": "What is the API key rotation policy?"},
        ),
        (
            "mcp_create_conversation_session.input.v1.json",
            {"title": "Support thread", "collection_id": "docs"},
        ),
        (
            "mcp_get_conversation_history.input.v1.json",
            {"session_id": "550e8400-e29b-41d4-a716-446655440000"},
        ),
        (
            "mcp_access_token_mint.request.v1.json",
            {"tenant_id": "acme", "principal": "user:alice", "role_template": "user"},
        ),
        (
            "mcp_list_indexed_documents.input.v1.json",
            {"tenant_id": "acme", "collection_id": "payments-api"},
        ),
        (
            "mcp_get_document_metadata.input.v1.json",
            {"document_id": "admin-guide", "collection_id": "payments-api"},
        ),
        (
            "mcp_visualize_document_graph.input.v1.json",
            {"document_id": "admin-guide", "collection_id": "payments-api"},
        ),
    ],
)
def test_mcp_input_schemas_validate(schema_name: str, sample: dict) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    jsonschema.validate(sample, schema)
