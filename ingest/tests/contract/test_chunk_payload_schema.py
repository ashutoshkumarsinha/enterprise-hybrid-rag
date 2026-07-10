"""Validate ingest chunk output against kernel schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from app.chunk_builder import blocks_to_chunks
from app.parsers.base import ParseContext, ParsedBlock
from app.pipeline import parse_document

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "modules" / "schemas" / "chunk_payload.v1.json"


@pytest.fixture(scope="module")
def chunk_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_blocks_to_chunks_validate(chunk_schema: dict) -> None:
    ctx = ParseContext(
        tenant_id="acme",
        collection_id="docs",
        document_id="guide",
        version_id="2026-01-01",
        title="Guide",
    )
    chunks = blocks_to_chunks(
        [ParsedBlock(text="Rotate API keys monthly.", section_title="Security")],
        ctx,
    )
    assert len(chunks) == 1
    jsonschema.validate(chunks[0], chunk_schema)


def test_parse_markdown_document(tmp_path: Path, chunk_schema: dict) -> None:
    source = tmp_path / "policy.md"
    source.write_text("# Refunds\n\nRefunds within 30 days.\n\n## Exceptions\n\nNone.\n", encoding="utf-8")
    ctx = ParseContext(
        tenant_id="acme",
        collection_id="docs",
        document_id="policy",
        version_id="v1",
        title="Refund Policy",
    )
    chunks = parse_document(source, ctx=ctx)
    assert len(chunks) >= 2
    for chunk in chunks:
        jsonschema.validate(chunk, chunk_schema)
