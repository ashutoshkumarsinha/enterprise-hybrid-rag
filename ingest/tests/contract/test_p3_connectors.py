"""E-31 Confluence / SharePoint connector contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONNECTORS = REPO_ROOT / "ingest" / "app" / "connectors"


def test_sharepoint_and_confluence_modules_exist() -> None:
    assert (CONNECTORS / "sharepoint.py").is_file()
    assert (CONNECTORS / "confluence.py").is_file()


def test_connectors_registered_in_factory() -> None:
    from app.connectors import get_connector

    sp = get_connector("sharepoint", tenant_id="acme", collection_id="docs")
    cf = get_connector("confluence", tenant_id="acme", collection_id="wiki")
    assert sp.__class__.__name__ == "SharePointConnector"
    assert cf.__class__.__name__ == "ConfluenceConnector"


def test_stub_connectors_list_and_fetch() -> None:
    from app.connectors import get_connector

    sp = get_connector("sharepoint", tenant_id="acme", collection_id="docs")
    objects = list(sp.list_objects())
    assert objects
    payload = sp.fetch_bytes(objects[0].key)
    assert b"Stub SharePoint" in payload


def test_connectors_doc_lists_e31() -> None:
    text = (REPO_ROOT / "ingest" / "docs" / "CONNECTORS.md").read_text(encoding="utf-8")
    assert "E-31" in text
    assert "confluence_enabled" in text
