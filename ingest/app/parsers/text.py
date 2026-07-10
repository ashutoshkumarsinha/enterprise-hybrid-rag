"""Plain text parser — paragraph and sliding-window chunks."""

from __future__ import annotations

import re
from pathlib import Path

from app.parsers.base import ParsedBlock


def parse_text_file(path: Path) -> list[ParsedBlock]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if not paragraphs:
        return [ParsedBlock(text=raw.strip() or "(empty document)")]
    return [ParsedBlock(text=p) for p in paragraphs]
