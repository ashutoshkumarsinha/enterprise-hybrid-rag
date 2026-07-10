"""DOCX fast path — python-docx."""

from __future__ import annotations

import os
from pathlib import Path

from app.parsers.base import ParsedBlock


def parse_docx_file(path: Path) -> list[ParsedBlock]:
    if os.environ.get("PARSER_STUB", "").lower() in ("true", "1", "yes"):
        return [ParsedBlock(text=f"Stub DOCX content for {path.name}", section_title="Section 1")]
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError("python-docx required for DOCX parsing") from exc

    doc = Document(str(path))
    blocks: list[ParsedBlock] = []
    current_title = "Document"
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            blocks.append(ParsedBlock(text="\n".join(buffer), section_title=current_title))
            buffer.clear()

    for para in doc.paragraphs:
        style = (para.style.name if para.style else "") or ""
        text = para.text.strip()
        if not text:
            continue
        if style.lower().startswith("heading"):
            flush()
            current_title = text
        else:
            buffer.append(text)
    flush()
    return blocks or [ParsedBlock(text="(empty docx)", section_title="Document")]
