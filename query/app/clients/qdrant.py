"""Qdrant hybrid retrieve client (dense + sparse RRF).

Spec: §4.5 · FR-02 tenant filter · query/docs/PERFORMANCE.md §4.
"""

from __future__ import annotations

import os
from typing import Any

from app.clients.embed import EmbedClient
from app.qdrant_collection import resolve_qdrant_collection


class QdrantClient:
    """Hybrid retrieval against the enterprise_hybrid_rag collection."""

    def __init__(
        self,
        *,
        url: str | None = None,
        grpc_port: int | None = None,
        collection: str | None = None,
        prefer_grpc: bool | None = None,
        search_ef: int | None = None,
        recall_limit: int | None = None,
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
        self._stub = os.environ.get("QDRANT_STUB", "").lower() in ("true", "1", "yes") or not self.url
        self.prefer_grpc = prefer and not self._stub
        self.search_ef = search_ef or int(os.environ.get("QDRANT_SEARCH_EF", "128"))
        self.recall_limit = recall_limit or int(os.environ.get("FINAL_RECALL_LIMIT", "25"))
        self._client = None
        if not self._stub:
            from qdrant_client import QdrantClient as QdrantSDK

            if self.prefer_grpc:
                host = self.url.replace("http://", "").replace("https://", "").split(":")[0]
                self._client = QdrantSDK(host=host, grpc_port=self.grpc_port, prefer_grpc=True)
            else:
                self._client = QdrantSDK(url=self.url)

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

    def hybrid_search(
        self,
        *,
        tenant_id: str,
        dense_vector: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        collection_id: str | None = None,
        additional_collection_ids: list[str] | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if self._stub:
            return _stub_chunks(tenant_id, collection_id, document_id)
        assert self._client is not None
        from qdrant_client import models

        physical = resolve_qdrant_collection(tenant_id=tenant_id, base=self._base_collection)
        must: list[models.FieldCondition] = [
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=tenant_id),
            )
        ]
        scope_ids = _scope_collection_ids(collection_id, additional_collection_ids)
        if scope_ids:
            if len(scope_ids) == 1:
                must.append(
                    models.FieldCondition(
                        key="collection_id",
                        match=models.MatchValue(value=scope_ids[0]),
                    )
                )
            else:
                must.append(
                    models.FieldCondition(
                        key="collection_id",
                        match=models.MatchAny(any=scope_ids),
                    )
                )
        if document_id:
            must.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                )
            )
        if version_id:
            must.append(
                models.FieldCondition(
                    key="version_id",
                    match=models.MatchValue(value=version_id),
                )
            )
        query_filter = models.Filter(must=must)
        sparse = models.SparseVector(indices=sparse_indices, values=sparse_values)
        result = self._client.query_points(
            collection_name=physical,
            prefetch=[
                models.Prefetch(query=dense_vector, limit=self.recall_limit * 2),
                models.Prefetch(
                    query=sparse,
                    using="bm25-text",
                    limit=self.recall_limit * 2,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=limit or self.recall_limit,
            search_params=models.SearchParams(hnsw_ef=self.search_ef),
            with_payload=True,
        )
        return [_point_to_chunk(point) for point in result.points]


def _scope_collection_ids(
    collection_id: str | None,
    additional_collection_ids: list[str] | None,
) -> list[str]:
    ids: list[str] = []
    if collection_id:
        ids.append(collection_id)
    for item in additional_collection_ids or []:
        if item and item not in ids:
            ids.append(item)
    return ids


def _point_to_chunk(point: Any) -> dict[str, Any]:
    payload = point.payload or {}
    collection_id = payload.get("collection_id", "")
    document_id = payload.get("document_id", "")
    title = payload.get("title") or payload.get("section_title") or document_id
    score = getattr(point, "score", None)
    return {
        "uuid": str(payload.get("uuid", point.id)),
        "tenant_id": payload.get("tenant_id"),
        "collection_id": collection_id,
        "document_id": document_id,
        "version_id": payload.get("version_id"),
        "section_title": payload.get("section_title") or title,
        "title": title,
        "text": payload.get("text", ""),
        "type": payload.get("type", "text"),
        "score": score,
        "label": f"{collection_id} / {document_id}" + (
            f" §{payload.get('section_title')}" if payload.get("section_title") else ""
        ),
    }


def _stub_chunks(
    tenant_id: str,
    collection_id: str | None,
    document_id: str | None,
) -> list[dict[str, Any]]:
    return [
        {
            "uuid": "00000000-0000-4000-8000-000000000001",
            "tenant_id": tenant_id,
            "collection_id": collection_id or "stub-collection",
            "document_id": document_id or "stub-doc",
            "version_id": "v1",
            "section_title": "Stub section",
            "title": "Stub document",
            "text": "Stub retrieved chunk for development.",
            "type": "text",
            "score": 0.85,
            "label": f"{collection_id or 'stub-collection'} / {document_id or 'stub-doc'}",
        }
    ]


def retrieve_for_state(
    state: dict[str, Any],
    embed_client: EmbedClient | None = None,
    qdrant_client: QdrantClient | None = None,
) -> list[dict[str, Any]]:
    """Embed query if needed and run hybrid search from RAG state."""
    embed_client = embed_client or EmbedClient()
    qdrant = qdrant_client or QdrantClient()
    dense = state.get("query_dense_vector")
    sparse = state.get("query_sparse_vector")
    if dense is None or sparse is None:
        query = state.get("query", "")
        dense = embed_client.embed(query)
        sparse = embed_client.sparse_from_text(query)
    return qdrant.hybrid_search(
        tenant_id=state.get("tenant_id", ""),
        dense_vector=dense,
        sparse_indices=sparse["indices"],
        sparse_values=sparse["values"],
        collection_id=state.get("collection_id") or None,
        additional_collection_ids=state.get("additional_collection_ids"),
        document_id=state.get("document_id"),
        version_id=state.get("version_id"),
    )
