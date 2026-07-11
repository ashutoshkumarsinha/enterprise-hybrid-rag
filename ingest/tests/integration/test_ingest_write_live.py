"""Ingest write path against live Qdrant + embed."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import hashlib

from app.dedup_store import reset_dedup_store
from app.writers import write_chunks

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "chunks" / "e2e-api-keys.json"


def _unique_fixture() -> dict:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    suffix = uuid.uuid4().hex[:8]
    data["document_id"] = f"{data['document_id']}-{suffix}"
    for idx, chunk in enumerate(data["chunks"], start=1):
        chunk["uuid"] = str(uuid.uuid4())
        chunk["document_id"] = data["document_id"]
        chunk["chunk_index"] = idx
        chunk["content_hash"] = hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest()
    return data


def test_write_fixture_chunks_to_qdrant(ingest_live_ready: None) -> None:
    reset_dedup_store()
    fixture = _unique_fixture()
    result = write_chunks(fixture["chunks"])
    assert result["validated"] == len(fixture["chunks"])
    assert result["written"] == len(fixture["chunks"])
    assert result.get("stub") is False
