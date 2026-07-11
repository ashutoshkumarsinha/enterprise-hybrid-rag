"""Federated catalog reads across regional MCP peers — E-32."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from app.catalog_store import CatalogStore, DocumentRow


def federated_mcp_enabled() -> bool:
    return os.environ.get("FEDERATED_MCP_ENABLED", "").lower() in ("true", "1", "yes")


def mcp_region() -> str:
    return os.environ.get("MCP_REGION", "us-east-1")


def peer_endpoints() -> dict[str, str]:
    raw = os.environ.get("MCP_PEER_ENDPOINTS_JSON", "{}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


class FederatedCatalogStore(CatalogStore):
    """Merge local catalog reads with optional regional peer query nodes."""

    def __init__(self, local: CatalogStore) -> None:
        self._local = local
        self._peers = peer_endpoints()

    def healthcheck(self) -> bool:
        return self._local.healthcheck()

    def list_indexed_documents(
        self,
        *,
        tenant_id: str,
        principal: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[DocumentRow], str | None]:
        docs, next_cursor = self._local.list_indexed_documents(
            tenant_id=tenant_id,
            principal=principal,
            collection_id=collection_id,
            document_id=document_id,
            limit=limit,
            cursor=cursor,
        )
        if not self._peers or document_id:
            return docs, next_cursor
        merged = {doc.get("document_id", ""): doc for doc in docs}
        for region, base_url in self._peers.items():
            if region == mcp_region():
                continue
            for peer_doc in _fetch_peer_documents(
                base_url,
                tenant_id=tenant_id,
                collection_id=collection_id,
                limit=limit,
            ):
                merged.setdefault(peer_doc.get("document_id", ""), peer_doc)
        out = list(merged.values())[:limit]
        return out, next_cursor

    def get_document_metadata(
        self,
        *,
        tenant_id: str,
        principal: str,
        document_id: str,
        collection_id: str | None = None,
        version_id: str | None = None,
    ) -> DocumentRow | None:
        local = self._local.get_document_metadata(
            tenant_id=tenant_id,
            principal=principal,
            document_id=document_id,
            collection_id=collection_id,
            version_id=version_id,
        )
        if local is not None:
            return local
        for region, base_url in self._peers.items():
            if region == mcp_region():
                continue
            peer = _fetch_peer_metadata(
                base_url,
                tenant_id=tenant_id,
                document_id=document_id,
                collection_id=collection_id,
                version_id=version_id,
            )
            if peer is not None:
                return peer
        return None


def _fetch_peer_documents(
    base_url: str,
    *,
    tenant_id: str,
    collection_id: str | None,
    limit: int,
) -> list[DocumentRow]:
    if os.environ.get("FEDERATED_MCP_STUB", "").lower() in ("true", "1", "yes"):
        return []
    url = f"{base_url.rstrip('/')}/mcp/tools/list_indexed_documents"
    body = {"tenant_id": tenant_id, "limit": limit}
    if collection_id:
        body["collection_id"] = collection_id
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return []
    docs = payload.get("documents") or payload.get("items") or []
    return [d for d in docs if isinstance(d, dict)]


def _fetch_peer_metadata(
    base_url: str,
    *,
    tenant_id: str,
    document_id: str,
    collection_id: str | None,
    version_id: str | None,
) -> DocumentRow | None:
    if os.environ.get("FEDERATED_MCP_STUB", "").lower() in ("true", "1", "yes"):
        return None
    url = f"{base_url.rstrip('/')}/mcp/tools/get_document_metadata"
    body: dict[str, Any] = {"tenant_id": tenant_id, "document_id": document_id}
    if collection_id:
        body["collection_id"] = collection_id
    if version_id:
        body["version_id"] = version_id
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    doc = payload.get("document") or payload.get("metadata")
    return doc if isinstance(doc, dict) else None
