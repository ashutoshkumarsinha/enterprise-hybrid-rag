"""Graph context block formatting."""

from __future__ import annotations

from app.graph_enrich import build_context_blocks, format_context_block


def test_format_context_block_includes_lineage_and_refs() -> None:
    chunk = {
        "collection_id": "payments-api",
        "document_id": "admin-guide",
        "section_title": "3.2.1",
        "title": "Authentication",
        "text": "Use API keys.",
        "score": 0.87,
    }
    meta = {
        "lineage": ["Chapter 3", "3.2 Authentication"],
        "cross_refs": ["refund-policy", "api-keys"],
    }
    block = format_context_block(chunk, meta)
    assert "payments-api / admin-guide" in block
    assert "*Lineage:*" in block
    assert "refund-policy" in block
    assert "Raw Source Block Content:" in block
    assert "Use API keys." in block


def test_build_context_blocks_preserves_order() -> None:
    chunks = [
        {"uuid": "a", "collection_id": "c", "document_id": "d1", "text": "one", "score": 0.9},
        {"uuid": "b", "collection_id": "c", "document_id": "d2", "text": "two", "score": 0.8},
    ]
    blocks = build_context_blocks(chunks, {})
    assert len(blocks) == 2
    assert "one" in blocks[0]
    assert "two" in blocks[1]
