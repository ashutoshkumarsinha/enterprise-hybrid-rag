"""Catalog document registry tests."""

from __future__ import annotations

import pytest

from app.catalog_store import InMemoryCatalogStore, reset_catalog_store


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_catalog_store()


def test_record_from_chunks_groups_by_document() -> None:
    store = InMemoryCatalogStore()
    chunks = [
        {
            "uuid": "a",
            "tenant_id": "acme",
            "collection_id": "payments-api",
            "document_id": "guide",
            "version_id": "v1",
            "title": "Guide",
            "text": "one",
            "content_hash": "h1",
            "source_uri": "file:///guide.md",
            "source_system": "filesystem",
        },
        {
            "uuid": "b",
            "tenant_id": "acme",
            "collection_id": "payments-api",
            "document_id": "guide",
            "version_id": "v1",
            "title": "Guide",
            "text": "two",
            "content_hash": "h2",
            "source_uri": "file:///guide.md",
            "source_system": "filesystem",
        },
    ]
    result = store.record_from_chunks(chunks, job_id="job-1")
    assert result["documents_recorded"] == 1
    doc = store._documents[("acme", "payments-api", "guide")]
    assert doc["latest_version_id"] == "v1"
    ver = store._versions[("acme", "payments-api", "guide", "v1")]
    assert ver["chunk_count"] == 2
    assert ver["ingest_job_id"] == "job-1"


def test_write_chunks_records_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_WRITE_STUB", "true")
    from app.writers import write_chunks

    chunks = [
        {
            "uuid": "a",
            "tenant_id": "acme",
            "collection_id": "payments-api",
            "document_id": "policy",
            "version_id": "v2",
            "title": "Policy",
            "text": "body",
            "content_hash": "abc",
        }
    ]
    result = write_chunks(chunks, job_id="job-99")
    assert result["documents_recorded"] == 1
