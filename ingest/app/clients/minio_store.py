"""MinIO object purge for tenant offboarding — E-21."""

from __future__ import annotations

import os


class MinioStore:
    """Delete object-store prefixes for a tenant."""

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
        bucket: str | None = None,
        staging_bucket: str | None = None,
    ) -> None:
        self.endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", "")
        self.access_key = access_key or os.environ.get("MINIO_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("MINIO_SECRET_KEY", "")
        self.region = region or os.environ.get("MINIO_REGION", "us-east-1")
        self.bucket = bucket or os.environ.get("MINIO_BUCKET", "hybrid-rag")
        self.staging_bucket = staging_bucket or os.environ.get("MINIO_BUCKET_STAGING", "hybrid-rag-staging")
        self._stub = os.environ.get("MINIO_STUB", "").lower() in ("true", "1", "yes") or not self.endpoint
        self._client = None
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

    def purge_tenant_prefix(self, tenant_id: str) -> int:
        """Delete `{tenant_id}/` objects from primary and staging buckets."""
        prefix = f"{tenant_id}/"
        if self._stub:
            return 0
        assert self._client is not None
        deleted = 0
        for bucket in {self.bucket, self.staging_bucket}:
            deleted += self._delete_prefix(bucket=bucket, prefix=prefix)
        return deleted

    def _delete_prefix(self, *, bucket: str, prefix: str) -> int:
        assert self._client is not None
        deleted = 0
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if not keys:
                continue
            self._client.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            deleted += len(keys)
        return deleted
