"""batch_write task orchestration."""

from __future__ import annotations

import os

from app.tasks import batch_write
from app.writers import write_chunks


def test_write_chunks_stub_mode() -> None:
    os.environ["INGEST_WRITE_STUB"] = "true"
    chunks = [
        {
            "uuid": "00000000-0000-4000-8000-000000000001",
            "tenant_id": "acme",
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": "v1",
            "title": "Guide",
            "text": "Rotate API keys monthly.",
            "type": "text",
            "ingested_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    result = write_chunks(chunks)
    assert result["validated"] == 1
    assert result["written"] == 0
    assert result["stub"] is True


def test_write_chunks_live_stub_stores() -> None:
    os.environ["INGEST_WRITE_STUB"] = "false"
    os.environ["EMBED_STUB"] = "true"
    os.environ["QDRANT_STUB"] = "true"
    os.environ["NEO4J_STUB"] = "true"
    os.environ["DEDUP_ENABLED"] = "true"
    from app.dedup_store import reset_dedup_store

    reset_dedup_store()
    chunks = [
        {
            "uuid": "00000000-0000-4000-8000-000000000002",
            "tenant_id": "acme",
            "collection_id": "docs",
            "document_id": "guide",
            "version_id": "v1",
            "title": "Guide",
            "text": "Enable MFA for admins.",
            "type": "text",
            "ingested_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    result = write_chunks(chunks)
    assert result["validated"] == 1
    assert result["written"] == 1
    assert result["qdrant_written"] == 1
    assert result["neo4j_written"] == 1
    assert result["stub"] is True

    duplicate = write_chunks(chunks)
    assert duplicate["validated"] == 1
    assert duplicate["written"] == 0
    assert duplicate["skipped_dedup"] == 1


def test_batch_write_updates_job_status() -> None:
    os.environ["INGEST_WRITE_STUB"] = "false"
    os.environ["EMBED_STUB"] = "true"
    os.environ["QDRANT_STUB"] = "true"
    os.environ["NEO4J_STUB"] = "true"
    os.environ["DEDUP_ENABLED"] = "false"
    from app.dedup_store import reset_dedup_store
    from app.job_store import InMemoryJobStore, reset_job_store

    reset_dedup_store()
    reset_job_store()
    import app.job_store as job_store_module

    store = InMemoryJobStore()
    job_store_module._store = store
    job = store.create_job(tenant_id="acme", collection_id="docs", job_type="document")
    result = batch_write(
        [
            {
                "uuid": "00000000-0000-4000-8000-000000000010",
                "tenant_id": "acme",
                "collection_id": "docs",
                "document_id": "guide",
                "version_id": "v1",
                "title": "Guide",
                "text": "Unique job status text.",
                "type": "text",
                "ingested_at": "2026-01-01T00:00:00+00:00",
            }
        ],
        job_id=job["job_id"],
    )
    assert result["written"] == 1
    status = store.get_job(job["job_id"])
    assert status is not None
    assert status["status"] == "completed"
    assert status["chunk_count"] == 1


def test_batch_write_task() -> None:
    os.environ["INGEST_WRITE_STUB"] = "true"
    result = batch_write(
        [
            {
                "uuid": "00000000-0000-4000-8000-000000000003",
                "tenant_id": "acme",
                "collection_id": "docs",
                "document_id": "guide",
                "version_id": "v1",
                "title": "Guide",
                "text": "Audit logs weekly.",
                "type": "text",
                "ingested_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    )
    assert result["validated"] == 1
