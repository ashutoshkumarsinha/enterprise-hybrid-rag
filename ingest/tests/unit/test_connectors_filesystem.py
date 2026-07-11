"""Filesystem connector unit tests."""

from __future__ import annotations

from pathlib import Path

from app.connectors.filesystem import FilesystemConnector


def test_filesystem_lists_markdown(tmp_path: Path) -> None:
    base = tmp_path / "acme" / "docs" / "guide" / "v1" / "raw"
    base.mkdir(parents=True)
    doc = base / "guide.md"
    doc.write_text("# Guide\n\nHello world.\n", encoding="utf-8")
    connector = FilesystemConnector(
        root=tmp_path,
        tenant_id="acme",
        collection_id="docs",
    )
    objects = list(connector.list_objects())
    assert len(objects) == 1
    assert objects[0].document_id == "guide"
    assert b"Hello world" in connector.fetch_bytes(objects[0].key)
