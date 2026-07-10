"""Parser unit tests."""

from __future__ import annotations

import os
from pathlib import Path

from app.parsers.markdown import parse_markdown_file
from app.parsers.router import parse_file_blocks, resolve_parser_kind
from app.parsers.text import parse_text_file


def test_text_parser_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
    blocks = parse_text_file(path)
    assert len(blocks) == 2


def test_markdown_headings(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("# Intro\n\nHello\n\n## Details\n\nMore", encoding="utf-8")
    blocks = parse_markdown_file(path)
    assert len(blocks) == 2
    assert blocks[1].section_title == "Details"


def test_router_pdf_stub() -> None:
    os.environ["PARSER_STUB"] = "true"
    kind = resolve_parser_kind(Path("doc.pdf"), profile="fast")
    assert kind == "pdf"


def test_router_parse_json(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('[{"id": 1, "name": "alpha"}]', encoding="utf-8")
    blocks = parse_file_blocks(path)
    assert len(blocks) == 1
    assert "alpha" in blocks[0].text
