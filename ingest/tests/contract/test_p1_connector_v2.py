"""E-17 connector interface v2 contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONNECTORS = REPO_ROOT / "ingest" / "app" / "connectors"


def test_connector_protocol_methods() -> None:
    from app.connectors.base import Connector

    for method in ("list_objects", "fetch_bytes", "metadata"):
        assert hasattr(Connector, method)
        assert getattr(getattr(Connector, method), "__isabstractmethod__", False)


def test_s3_and_filesystem_connectors_registered() -> None:
    from app.connectors import get_connector

    fs = get_connector("filesystem", tenant_id="acme", collection_id="docs")
    s3 = get_connector("s3", tenant_id="acme", collection_id="docs")
    assert fs.__class__.__name__ == "FilesystemConnector"
    assert s3.__class__.__name__ == "S3Connector"


def test_connector_sync_pipeline_exists() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "connector_sync.py").read_text(encoding="utf-8")
    assert "sync_collection" in text
    assert "get_connector" in text
    assert "parse_document" in text
    assert "write_chunks" in text


def test_orchestrator_exposes_connector_sync_routes() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "orchestrator.py").read_text(encoding="utf-8")
    assert '"/admin/ingest/collection"' in text
    assert '"/admin/connectors/sync"' in text
    assert "enqueue_collection_sync" in text


def test_beat_schedule_supports_connector_sync() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "beat_config.py").read_text(encoding="utf-8")
    assert "CONNECTOR_BEAT_TARGETS" in text or "beat_targets" in text
