"""SharePoint connector — E-31 (stub-first, OAuth in production)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Iterator

from app.connectors.base import Connector, SourceObject


class SharePointConnector(Connector):
    """Lists and fetches documents from a SharePoint document library."""

    def __init__(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        site_url: str | None = None,
        library: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.collection_id = collection_id
        self.site_url = site_url or os.environ.get("SHAREPOINT_SITE_URL", "")
        self.library = library or os.environ.get("SHAREPOINT_LIBRARY", "Shared Documents")
        self._stub = os.environ.get("CONNECTOR_STUB", "").lower() in ("true", "1", "yes") or not self.site_url
        self._objects = _stub_objects(tenant_id, collection_id)

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
                    "source_system": "sharepoint",
                }
        return {}


def _stub_objects(tenant_id: str, collection_id: str) -> list[SourceObject]:
    doc = "policy-handbook"
    key = f"sharepoint://{tenant_id}/{collection_id}/{doc}.docx"
    return [
        SourceObject(
            key=key,
            document_id=doc,
            etag="sp-stub-etag-001",
            mtime=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
            size=2048,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    ]


def _stub_payload(document_id: str) -> bytes:
    return f"# {document_id}\n\nStub SharePoint export for connector tests.\n".encode("utf-8")
