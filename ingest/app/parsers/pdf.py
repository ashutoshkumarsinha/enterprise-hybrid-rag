"""PDF fast path — PyMuPDF."""

from __future__ import annotations

import os
from pathlib import Path

from app.parsers.base import ParsedBlock


def parse_pdf_file(path: Path) -> list[ParsedBlock]:
    if os.environ.get("PARSER_STUB", "").lower() in ("true", "1", "yes"):
        return [
            ParsedBlock(
                text=f"Stub PDF content for {path.name}",
                section_title="Page 1",
                page_number=1,
            )
        ]
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError("pymupdf required for PDF parsing (pip install pymupdf)") from exc

    blocks: list[ParsedBlock] = []
    with fitz.open(path) as doc:
        for page_no, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                blocks.append(
                    ParsedBlock(
                        text=text,
                        section_title=f"Page {page_no}",
                        section_id=f"page-{page_no}",
                        page_number=page_no,
                    )
                )
    return blocks or [ParsedBlock(text="(empty pdf)", page_number=1)]
