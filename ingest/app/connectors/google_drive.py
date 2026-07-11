"""Google Drive connector — E-31 extension (stub-first, OAuth in production)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Iterator

from app.connectors.base import Connector, SourceObject


class GoogleDriveConnector(Connector):
    """Syncs shared-drive files into ingest documents."""

    def __init__(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        drive_id: str | None = None,
        folder_id: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.collection_id = collection_id
        self.drive_id = drive_id or os.environ.get("GOOGLE_DRIVE_ID", "")
        self.folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
        self._stub = os.environ.get("CONNECTOR_STUB", "").lower() in ("true", "1", "yes") or not self.drive_id
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
                    "source_system": "google_drive",
                }
        return {}


def _stub_objects(tenant_id: str, collection_id: str) -> list[SourceObject]:
    doc = "team-playbook"
    key = f"gdrive://{tenant_id}/{collection_id}/{doc}.pdf"
    return [
        SourceObject(
            key=key,
            document_id=doc,
            etag="gd-stub-etag-001",
            mtime=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
            size=8192,
            content_type="application/pdf",
        )
    ]


def _stub_payload(document_id: str) -> bytes:
    return f"%PDF-stub {document_id}\n".encode("utf-8")
