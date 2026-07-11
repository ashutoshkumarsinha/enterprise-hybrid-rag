"""Connector factory."""

from __future__ import annotations

import os

from app.connectors.base import Connector
from app.connectors.confluence import ConfluenceConnector
from app.connectors.filesystem import FilesystemConnector
from app.connectors.s3 import S3Connector
from app.connectors.sharepoint import SharePointConnector


def get_connector(
    connector_type: str,
    *,
    tenant_id: str,
    collection_id: str,
    prefix: str | None = None,
) -> Connector:
    kind = connector_type.lower()
    if kind in ("filesystem", "fs", "local"):
        root = os.environ.get("DOCUMENTS_SOURCE_DIR", "/data/sources")
        return FilesystemConnector(
            root=root,
            tenant_id=tenant_id,
            collection_id=collection_id,
            prefix=prefix,
        )
    if kind in ("s3", "minio"):
        return S3Connector(
            tenant_id=tenant_id,
            collection_id=collection_id,
            prefix=prefix,
        )
    if kind in ("sharepoint", "sp"):
        return SharePointConnector(tenant_id=tenant_id, collection_id=collection_id)
    if kind in ("confluence", "cf"):
        return ConfluenceConnector(tenant_id=tenant_id, collection_id=collection_id)
    raise ValueError(f"unsupported connector type: {connector_type}")
