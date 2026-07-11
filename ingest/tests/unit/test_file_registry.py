"""File registry unit tests."""

from __future__ import annotations

from app.file_registry import InMemoryFileRegistry, registry_key


def test_registry_skips_unchanged_etag() -> None:
    registry = InMemoryFileRegistry()
    key = registry_key(tenant_id="acme", collection_id="docs", object_key="a/b.md")
    assert registry.should_ingest(registry_key=key, etag="etag-1") is True
    registry.mark_ingested(registry_key=key, etag="etag-1")
    assert registry.should_ingest(registry_key=key, etag="etag-1") is False
    assert registry.should_ingest(registry_key=key, etag="etag-2") is True
