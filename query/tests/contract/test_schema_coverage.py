"""E-15 kernel schema coverage — every modules/schemas/*.json has a contract sample."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = REPO_ROOT / "modules" / "schemas"

SCHEMA_SAMPLES: dict[str, dict] = {
    "chunk_payload.v1.json": {
        "uuid": "00000000-0000-4000-8000-000000000001",
        "tenant_id": "acme",
        "collection_id": "docs",
        "document_id": "guide",
        "version_id": "v1",
        "title": "Guide",
        "text": "Rotate API keys monthly.",
        "type": "text",
        "ingested_at": "2026-01-01T00:00:00+00:00",
    },
    "mcp_research_documents.input.v1.json": {
        "query": "What is the API key rotation policy?",
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
    },
    "mcp_create_conversation_session.input.v1.json": {
        "title": "Support thread",
        "collection_id": "docs",
    },
    "mcp_get_conversation_history.input.v1.json": {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
    },
    "mcp_list_conversation_sessions.input.v1.json": {
        "tenant_id": "acme",
        "limit": 20,
    },
    "mcp_list_indexed_documents.input.v1.json": {
        "tenant_id": "acme",
        "collection_id": "payments-api",
    },
    "mcp_get_document_metadata.input.v1.json": {
        "document_id": "admin-guide",
        "collection_id": "payments-api",
    },
    "mcp_visualize_document_graph.input.v1.json": {
        "document_id": "admin-guide",
        "collection_id": "payments-api",
    },
    "mcp_access_token_mint.request.v1.json": {
        "tenant_id": "acme",
        "principal": "user:alice",
        "role_template": "user",
    },
    "mcp_access_token_mint.response.v1.json": {
        "token_id": "550e8400-e29b-41d4-a716-446655440000",
        "access_token": "rag_mcp_550e8400-e29b-41d4-a716-446655440000.AbCdEfGh",
        "tenant_id": "acme",
        "principal": "user:alice",
        "permissions": ["mcp:research_documents"],
        "created_at": "2026-07-09T20:00:00Z",
    },
    "events.ingest_completed.v1.json": {
        "event": "ingest.completed",
        "schema_version": 1,
        "tenant_id": "acme-corp",
        "collection_id": "payments-api",
        "version_id": "2026-03-01",
        "job_id": "550e8400-e29b-41d4-a716-446655440000",
        "chunk_count": 12400,
        "error_count": 0,
        "cache_bump": True,
        "timestamp": "2026-07-09T20:00:00Z",
    },
}


def test_all_kernel_schemas_have_contract_samples() -> None:
    schema_files = sorted(p.name for p in SCHEMAS.glob("*.json"))
    assert schema_files, "no kernel schemas found"
    missing = [name for name in schema_files if name not in SCHEMA_SAMPLES]
    assert not missing, f"missing contract samples for: {missing}"


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_SAMPLES))
def test_kernel_schema_validates_sample(schema_name: str) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    jsonschema.validate(SCHEMA_SAMPLES[schema_name], schema)
