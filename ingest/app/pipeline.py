"""Ingest parse pipeline — file to validated chunk payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.chunk_builder import blocks_to_chunks
from app.parsers.base import ParseContext
from app.parsers.router import parse_file_blocks


def parse_document(
    path: Path | str,
    *,
    ctx: ParseContext,
    manifest_parser: str | None = None,
) -> list[dict[str, Any]]:
    """Parse a source file into kernel chunk payloads (§4.2)."""
    blocks = parse_file_blocks(
        path,
        profile=ctx.parser_profile,
        manifest_parser=manifest_parser,
    )
    return blocks_to_chunks(blocks, ctx)
