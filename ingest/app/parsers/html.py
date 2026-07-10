"""HTML parser — lightweight tag strip (trafilatura optional)."""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

from app.parsers.base import ParsedBlock


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(re.sub(r"\s+", " ", text))
    return text.strip()


def parse_html_file(path: Path) -> list[ParsedBlock]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        import trafilatura

        extracted = trafilatura.extract(raw, include_comments=False, include_tables=True)
        if extracted and extracted.strip():
            return [ParsedBlock(text=extracted.strip(), section_title="HTML")]
    except ImportError:
        pass
    text = _strip_html(raw)
    return [ParsedBlock(text=text or raw[:4000], section_title="HTML")]
