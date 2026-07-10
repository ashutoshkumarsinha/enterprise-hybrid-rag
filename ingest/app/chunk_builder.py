"""Build normative Qdrant chunk payloads from parser blocks."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from app.parsers.base import ParseContext, ParsedBlock

DEFAULT_MAX_CHARS = 2048
DEFAULT_OVERLAP_CHARS = 256


def _max_chars() -> int:
    token_limit = int(os.environ.get("MAX_CHUNK_TOKENS", "512"))
    return int(os.environ.get("MAX_CHUNK_CHARS", str(token_limit * 4)))


def _overlap_chars() -> int:
    token_overlap = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "64"))
    return int(os.environ.get("CHUNK_OVERLAP_CHARS", str(token_overlap * 4)))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_text(text: str, *, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return parts


def blocks_to_chunks(blocks: list[ParsedBlock], ctx: ParseContext) -> list[dict[str, Any]]:
    """Convert parsed blocks into ``chunk_payload.v1`` dicts."""
    ingested_at = datetime.now(UTC).isoformat()
    max_chars = _max_chars()
    overlap = _overlap_chars()
    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for block in blocks:
        for piece in _split_text(block.text, max_chars=max_chars, overlap=overlap):
            chunk_index += 1
            payload: dict[str, Any] = {
                "uuid": str(uuid.uuid4()),
                "tenant_id": ctx.tenant_id,
                "collection_id": ctx.collection_id,
                "document_id": ctx.document_id,
                "version_id": ctx.version_id,
                "title": ctx.title,
                "text": piece,
                "chunk_index": chunk_index,
                "type": block.block_type,
                "tags": list(ctx.tags),
                "source_system": ctx.source_system,
                "references": list(block.references),
                "ingested_at": ingested_at,
                "content_hash": content_hash(piece),
            }
            if ctx.source_uri:
                payload["source_uri"] = ctx.source_uri
            if block.section_id:
                payload["section_id"] = block.section_id
            if block.section_title:
                payload["section_title"] = block.section_title
            if block.parent_section_id:
                payload["parent_section_id"] = block.parent_section_id
            if block.page_number is not None:
                payload["page_number"] = block.page_number
            chunks.append(payload)
    return chunks
