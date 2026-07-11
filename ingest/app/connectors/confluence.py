"""Confluence connector — E-31 (stub-first, API token in production)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Iterator

from app.connectors.base import Connector, SourceObject


class ConfluenceConnector(Connector):
    """Syncs Confluence page tree into documents for ingest."""

    def __init__(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        base_url: str | None = None,
        space_key: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.collection_id = collection_id
        self.base_url = base_url or os.environ.get("CONFLUENCE_BASE_URL", "")
        self.space_key = space_key or os.environ.get("CONFLUENCE_SPACE_KEY", "")
        self._stub = os.environ.get("CONNECTOR_STUB", "").lower() in ("true", "1", "yes") or not self.base_url
        self._objects = _stub_objects(tenant_id, collection_id, self.space_key or "ENG")

    @property
    def is_stub(self) -> bool:
        return self._stub

    def list_objects(self, since: datetime | None = None) -> Iterator[SourceObject]:
        for obj in self._objects:
            if since and obj.mtime and obj.mtime < since:
                continue
            yield obj

    def fetch_bytes(self, key: str) -> bytes:
        for obj in self._objects:
            if obj.key == key:
                return _stub_payload(obj.document_id)
        raise FileNotFoundError(key)

    def metadata(self, key: str) -> dict[str, str]:
        for obj in self._objects:
            if obj.key == key:
                return {
                    "etag": obj.etag or "",
                    "mtime": obj.mtime.isoformat() if obj.mtime else "",
                    "size": str(obj.size),
                    "source_system": "confluence",
                }
        return {}


def _stub_objects(tenant_id: str, collection_id: str, space_key: str) -> list[SourceObject]:
    doc = "runbook-oncall"
    key = f"confluence://{tenant_id}/{collection_id}/{space_key}/{doc}"
    return [
        SourceObject(
            key=key,
            document_id=doc,
            etag="cf-stub-etag-001",
            mtime=datetime(2026, 4, 2, 14, 30, tzinfo=UTC),
            size=4096,
            content_type="text/html",
        )
    ]


def _stub_payload(document_id: str) -> bytes:
    html = f"<h1>{document_id}</h1><p>Stub Confluence page for connector tests.</p>"
    return html.encode("utf-8")
