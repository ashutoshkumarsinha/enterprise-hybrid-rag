"""Connector sync pipeline."""

from __future__ import annotations

import os

import pytest

from app.connector_sync import sync_collection
from app.file_registry import reset_file_registry


@pytest.fixture(autouse=True)
def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNECTOR_STUB", "true")
    monkeypatch.setenv("INGEST_WRITE_STUB", "false")
    monkeypatch.setenv("EMBED_STUB", "true")
    monkeypatch.setenv("QDRANT_STUB", "true")
    monkeypatch.setenv("NEO4J_STUB", "true")
    monkeypatch.delenv("REDIS_URL", raising=False)
    reset_file_registry()


def test_sync_collection_ingests_stub_object() -> None:
    result = sync_collection(
        tenant_id="acme",
        collection_id="payments-api",
        version_id="v1",
        connector="s3",
        mode="full",
    )
    assert result["ingested"] == 1
    assert result["chunk_count"] >= 1
    assert result["status"] == "completed"


def test_incremental_skips_second_run() -> None:
    first = sync_collection(
        tenant_id="acme",
        collection_id="payments-api",
        version_id="v1",
        connector="s3",
        mode="incremental",
    )
    second = sync_collection(
        tenant_id="acme",
        collection_id="payments-api",
        version_id="v1",
        connector="s3",
        mode="incremental",
    )
    assert first["ingested"] == 1
    assert second["skipped"] == 1
    assert second["ingested"] == 0
