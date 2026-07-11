"""Qdrant upsert client for ingest writes."""

from __future__ import annotations

import os
from typing import Any

from qdrant_client import models

from app.qdrant_collection import resolve_qdrant_collection

_INDEX_FIELDS = (
    "tenant_id",
    "collection_id",
    "document_id",
    "version_id",
    "type",
    "acl_principal",
)


class QdrantWriter:
    """Batch upsert chunk payloads with dense + sparse vectors."""

    def __init__(
        self,
        *,
        url: str | None = None,
        grpc_port: int | None = None,
        collection: str | None = None,
        prefer_grpc: bool | None = None,
        upsert_batch: int | None = None,
    ) -> None:
        self.url = url or os.environ.get("QDRANT_URL", "")
        self.grpc_port = grpc_port or int(os.environ.get("QDRANT_GRPC_PORT", "6334"))
        self.collection = collection or os.environ.get(
            "QDRANT_COLLECTION", "enterprise_hybrid_rag"
        )
        self._base_collection = self.collection
        prefer = prefer_grpc if prefer_grpc is not None else os.environ.get(
            "PREFER_QDRANT_GRPC", ""
        ).lower() in ("true", "1", "yes")
        self.upsert_batch = upsert_batch or int(os.environ.get("QDRANT_UPSERT_BATCH", "100"))
        self._stub = os.environ.get("QDRANT_STUB", "").lower() in ("true", "1", "yes") or not self.url
        self.prefer_grpc = prefer and not self._stub
        self._client = None
        self._indexes_ensured = False
        if not self._stub:
            from qdrant_client import QdrantClient

            if self.prefer_grpc:
                host = self.url.replace("http://", "").replace("https://", "").split(":")[0]
                self._client = QdrantClient(host=host, grpc_port=self.grpc_port, prefer_grpc=True)
            else:
                self._client = QdrantClient(url=self.url)

    @property
    def transport(self) -> str:
        if self._stub:
            return "stub"
        return "grpc" if self.prefer_grpc else "rest"

    @property
    def is_stub(self) -> bool:
        return self._stub

    def healthcheck(self) -> bool:
        if self._stub:
            return True
        try:
            assert self._client is not None
            self._client.get_collections()
            return True
        except Exception:
            return False

    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        *,
        dense_vectors: list[list[float]],
        sparse_vectors: list[dict[str, Any]],
    ) -> int:
        """Upsert points; returns count accepted."""
        if not chunks:
            return 0
        tenant_id = str(chunks[0].get("tenant_id", ""))
        physical = resolve_qdrant_collection(tenant_id=tenant_id, base=self._base_collection)
        if self._stub:
            return len(chunks)
        assert self._client is not None
        self._ensure_payload_indexes(physical)
        written = 0
        for start in range(0, len(chunks), self.upsert_batch):
            batch_chunks = chunks[start : start + self.upsert_batch]
            batch_dense = dense_vectors[start : start + self.upsert_batch]
            batch_sparse = sparse_vectors[start : start + self.upsert_batch]
            points = [
                models.PointStruct(
                    id=chunk["uuid"],
                    vector={
                        "": dense,
                        "bm25-text": models.SparseVector(
                            indices=sparse["indices"],
                            values=sparse["values"],
                        ),
                    },
                    payload=chunk,
                )
                for chunk, dense, sparse in zip(batch_chunks, batch_dense, batch_sparse, strict=True)
            ]
            self._client.upsert(collection_name=physical, points=points, wait=False)
            written += len(points)
        return written

    def _ensure_payload_indexes(self, collection_name: str | None = None) -> None:
        target = collection_name or self.collection
        if self._indexes_ensured or self._stub:
            return
        assert self._client is not None
        for field in _INDEX_FIELDS:
            try:
                self._client.create_payload_index(
                    collection_name=target,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass
        self._indexes_ensured = True

    def delete_version(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        document_id: str,
        version_id: str,
        expected_points: int | None = None,
    ) -> int:
        """Delete Qdrant points for a document version; returns deleted estimate."""
        if self._stub:
            return int(expected_points or 0)
        assert self._client is not None
        physical = resolve_qdrant_collection(tenant_id=tenant_id, base=self._base_collection)
        self._client.delete(
            collection_name=physical,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                        models.FieldCondition(
                            key="collection_id",
                            match=models.MatchValue(value=collection_id),
                        ),
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        ),
                        models.FieldCondition(
                            key="version_id",
                            match=models.MatchValue(value=version_id),
                        ),
                    ]
                )
            ),
            wait=True,
        )
        return int(expected_points or 0)

    def delete_tenant(self, *, tenant_id: str, expected_points: int | None = None) -> int:
        """Delete all Qdrant points for a tenant."""
        if self._stub:
            return int(expected_points or 0)
        assert self._client is not None
        physical = resolve_qdrant_collection(tenant_id=tenant_id, base=self._base_collection)
        self._client.delete(
            collection_name=physical,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                    ]
                )
            ),
            wait=True,
        )
        return int(expected_points or 0)
