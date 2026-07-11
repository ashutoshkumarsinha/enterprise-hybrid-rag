"""E-15 ingest.completed event matches kernel JSON schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from app.events import build_ingest_completed_event

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "modules" / "schemas" / "events.ingest_completed.v1.json"


def test_build_ingest_completed_event_validates() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = build_ingest_completed_event(
        tenant_id="acme-corp",
        collection_id="payments-api",
        version_id="2026-03-01",
        job_id="550e8400-e29b-41d4-a716-446655440000",
        chunk_count=42,
        error_count=1,
        cache_bump=True,
        timestamp="2026-07-09T20:00:00Z",
    )
    jsonschema.validate(payload, schema)
    assert payload["event"] == "ingest.completed"
    assert payload["schema_version"] == 1
