"""S3 / MinIO connector for staging and production object sync."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from app.connectors.base import Connector, SourceObject
from app.connectors.filesystem import _document_id_from_key

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


class S3Connector(Connector):
    def __init__(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        prefix: str | None = None,
        bucket: str | None = None,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.collection_id = collection_id
        self.prefix = (prefix or f"{tenant_id}/{collection_id}/").lstrip("/")
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"
        self.bucket = bucket or os.environ.get("MINIO_BUCKET", "hybrid-rag")
        self.endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", "")
        self.access_key = access_key or os.environ.get("MINIO_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("MINIO_SECRET_KEY", "")
        self.region = region or os.environ.get("MINIO_REGION", "us-east-1")
        self._stub = os.environ.get("CONNECTOR_STUB", "").lower() in ("true", "1", "yes") or not self.endpoint
        self._client = None
        self._stub_objects = _stub_objects(tenant_id, collection_id, self.prefix)
        if not self._stub:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )

    @property
    def is_stub(self) -> bool:
        return self._stub

    def list_objects(self, since: datetime | None = None) -> Iterator[SourceObject]:
        if self._stub:
            for obj in self._stub_objects:
                if since and obj.mtime and obj.mtime < since:
                    continue
                yield obj
            return
        assert self._client is not None
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith("/"):
                    continue
                if Path(key).suffix.lower() not in _SUPPORTED_SUFFIXES:
                    continue
                mtime = item.get("LastModified")
                if since and mtime and mtime < since:
                    continue
                yield SourceObject(
                    key=key,
                    document_id=_document_id_from_key(key, self.tenant_id, self.collection_id),
                    etag=item.get("ETag", "").strip('"') or None,
                    mtime=mtime.astimezone(UTC) if mtime else None,
                    size=int(item.get("Size", 0)),
                )

    def fetch_bytes(self, key: str) -> bytes:
        if self._stub:
            for obj in self._stub_objects:
                if obj.key == key:
                    return _stub_payload(obj.document_id)
            raise FileNotFoundError(key)
        assert self._client is not None
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def metadata(self, key: str) -> dict[str, str]:
        if self._stub:
            for obj in self._stub_objects:
                if obj.key == key:
                    return {
                        "etag": obj.etag or "",
                        "mtime": obj.mtime.isoformat() if obj.mtime else "",
                        "size": str(obj.size),
                    }
            return {}
        assert self._client is not None
        response = self._client.head_object(Bucket=self.bucket, Key=key)
        mtime = response.get("LastModified")
        return {
            "etag": response.get("ETag", "").strip('"'),
            "mtime": mtime.astimezone(UTC).isoformat() if mtime else "",
            "size": str(response.get("ContentLength", 0)),
        }


def _stub_objects(tenant_id: str, collection_id: str, prefix: str) -> list[SourceObject]:
    doc = "refund-policy"
    key = f"{prefix}{doc}/v1/raw/{doc}.md"
    return [
        SourceObject(
            key=key,
            document_id=doc,
            etag="stub-etag-001",
            mtime=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            size=128,
        )
    ]


def _stub_payload(document_id: str) -> bytes:
    return f"# {document_id}\n\nStub connector document for offline tests.\n".encode("utf-8")
