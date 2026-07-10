"""Docling quality-tier adapter (optional dependency)."""

from __future__ import annotations

import os
from pathlib import Path

from app.parsers.base import ParsedBlock


def parse_docling_file(path: Path) -> list[ParsedBlock]:
    if os.environ.get("PARSER_STUB", "").lower() in ("true", "1", "yes"):
        return [
            ParsedBlock(
                text=f"Stub Docling content for {path.name}",
                section_title="Docling",
            )
        ]
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise ImportError(
            "docling not installed — pip install -r requirements-docling.txt"
        ) from exc

    converter = DocumentConverter()
    result = converter.convert(str(path))
    markdown = result.document.export_to_markdown()
    return [ParsedBlock(text=markdown.strip(), section_title="Docling", block_type="text")]
