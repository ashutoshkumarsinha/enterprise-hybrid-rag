"""Filesystem connector for dev and air-gapped ingest."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from app.connectors.base import Connector, SourceObject

_SUPPORTED_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".pdf",
    ".docx",
}


class FilesystemConnector(Connector):
    def __init__(
        self,
        *,
        root: str | Path,
        tenant_id: str,
        collection_id: str,
        prefix: str | None = None,
    ) -> None:
        self.root = Path(root)
        self.tenant_id = tenant_id
        self.collection_id = collection_id
        rel = prefix or f"{tenant_id}/{collection_id}"
        self.base = self.root / rel

    def list_objects(self, since: datetime | None = None) -> Iterator[SourceObject]:
        if not self.base.exists():
            return iter(())
        for path in sorted(self.base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if since and mtime < since:
                continue
            rel_key = str(path.relative_to(self.root)).replace("\\", "/")
            yield SourceObject(
                key=rel_key,
                document_id=_document_id_from_key(rel_key, self.tenant_id, self.collection_id),
                etag=_etag_for_path(path),
                mtime=mtime,
                size=path.stat().st_size,
                content_type=None,
            )

    def fetch_bytes(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def metadata(self, key: str) -> dict[str, str]:
        path = self.root / key
        stat = path.stat()
        return {
            "etag": _etag_for_path(path),
            "mtime": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            "size": str(stat.st_size),
        }


def _etag_for_path(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:16]


def _document_id_from_key(key: str, tenant_id: str, collection_id: str) -> str:
    parts = key.strip("/").split("/")
    if len(parts) >= 5 and parts[0] == tenant_id and parts[1] == collection_id:
        return parts[2]
    return Path(parts[-1]).stem
