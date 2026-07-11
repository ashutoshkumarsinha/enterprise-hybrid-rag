"""Tenant quota admin handlers — FR-30 / E-27."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from app.catalog_store import get_catalog_store
from app.quota_store import get_quota_store


async def put_tenant_quotas(tenant_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    limits = get_quota_store().upsert_quotas(tenant_id, body)
    return {"status": "ok", "quotas": limits.as_dict()}


def get_tenant_quotas(tenant_id: str) -> dict[str, Any]:
    limits = get_quota_store().get_quotas(tenant_id)
    usage = {
        "chunk_count": get_catalog_store().count_tenant_chunks(tenant_id),
        "collection_count": get_quota_store().count_collections(tenant_id),
    }
    return {"quotas": limits.as_dict(), "usage": usage}
