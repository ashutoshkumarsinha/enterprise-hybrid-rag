"""Shared parser types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParseContext:
    tenant_id: str
    collection_id: str
    document_id: str
    version_id: str
    title: str
    source_uri: str | None = None
    source_system: str = "filesystem"
    parser_profile: str = "fast"
    tags: list[str] = field(default_factory=list)


@dataclass
class ParsedBlock:
    text: str
    section_title: str | None = None
    section_id: str | None = None
    parent_section_id: str | None = None
    page_number: int | None = None
    block_type: str = "text"
    references: list[str] = field(default_factory=list)
