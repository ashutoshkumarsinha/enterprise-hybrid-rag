"""Markdown parser — ATX heading sections."""

from __future__ import annotations

import re
from pathlib import Path

from app.parsers.base import ParsedBlock

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def parse_markdown_file(path: Path) -> list[ParsedBlock]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    matches = list(_HEADING.finditer(raw))
    if not matches:
        return [ParsedBlock(text=raw.strip(), section_title="Document")]

    blocks: list[ParsedBlock] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        body = raw[start:end].strip()
        title = match.group(2).strip()
        section_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or f"section-{idx}"
        if body:
            blocks.append(
                ParsedBlock(
                    text=body,
                    section_title=title,
                    section_id=section_id,
                )
            )
    return blocks or [ParsedBlock(text=raw.strip(), section_title="Document")]
