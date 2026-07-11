"""Parser dispatch by extension and profile."""

from __future__ import annotations

import os
from pathlib import Path

from app.langsmith_config import ingest_traceable
from app.parsers.base import ParsedBlock
from app.parsers.docling import parse_docling_file
from app.parsers.docx import parse_docx_file
from app.parsers.html import parse_html_file
from app.parsers.markdown import parse_markdown_file
from app.parsers.pdf import parse_pdf_file
from app.parsers.structured import parse_csv_file, parse_json_file, parse_yaml_file
from app.parsers.text import parse_text_file

_EXTENSION_MAP = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".csv": "csv",
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "docling",
}


def resolve_parser_kind(path: Path, *, profile: str = "fast", manifest_parser: str | None = None) -> str:
    ext = path.suffix.lower()
    kind = _EXTENSION_MAP.get(ext, "text")
    if profile == "docling" or manifest_parser == "docling":
        if kind in ("pdf", "docx", "pptx"):
            return "docling"
    if profile == "auto" and manifest_parser == "docling":
        if kind in ("pdf", "docx", "pptx"):
            return "docling"
    return kind


@ingest_traceable("ingest.parser.parse_file", run_type="parser")
def parse_file_blocks(
    path: Path | str,
    *,
    profile: str = "fast",
    manifest_parser: str | None = None,
) -> list[ParsedBlock]:
    """Parse a file into text blocks before chunk payload assembly."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(str(source))

    kind = resolve_parser_kind(source, profile=profile, manifest_parser=manifest_parser)
    if kind == "markdown":
        return parse_markdown_file(source)
    if kind == "html":
        return parse_html_file(source)
    if kind == "json":
        return parse_json_file(source)
    if kind == "yaml":
        return parse_yaml_file(source)
    if kind == "csv":
        return parse_csv_file(source)
    if kind == "pdf":
        return parse_pdf_file(source)
    if kind == "docx":
        return parse_docx_file(source)
    if kind == "docling":
        return parse_docling_file(source)
    if kind == "text":
        return parse_text_file(source)

    if os.environ.get("PARSER_STUB", "").lower() in ("true", "1", "yes"):
        return [ParsedBlock(text=f"Stub parse for {source.name}", section_title="Document")]
    return parse_text_file(source)
