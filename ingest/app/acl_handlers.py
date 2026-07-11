"""ACL admin route handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.acl_store import get_acl_store
from app.events import publish_acl_changed


async def create_acl_grant(request: Request) -> dict[str, Any]:
    body = await request.json()
    tenant_id = body.get("tenant_id")
    principal = body.get("principal")
    collection_id = body.get("collection_id")
    document_id = body.get("document_id")
    permission = body.get("permission", "read")
    if not tenant_id or not principal:
        raise HTTPException(status_code=422, detail={"code": "validation"})
    store = get_acl_store()
    try:
        grant = store.create_grant(
            tenant_id=tenant_id,
            principal=principal,
            collection_id=collection_id,
            document_id=document_id,
            permission=permission,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "validation", "message": str(exc)}) from exc
    publish_acl_changed(tenant_id=tenant_id, grant_id=grant["grant_id"])
    return {"status": "created", "grant": grant, "stub": False}


def list_acl_grants(
    *,
    tenant_id: str,
    principal: str | None = None,
    collection_id: str | None = None,
) -> dict[str, Any]:
    if not tenant_id:
        raise HTTPException(status_code=422, detail={"code": "validation"})
    grants = get_acl_store().list_grants(
        tenant_id=tenant_id,
        principal=principal,
        collection_id=collection_id,
    )
    return {"tenant_id": tenant_id, "grants": grants, "count": len(grants), "stub": False}


def delete_acl_grant(grant_id: str) -> dict[str, Any]:
    deleted = get_acl_store().delete_grant(grant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found", "grant_id": grant_id})
    publish_acl_changed(tenant_id=deleted["tenant_id"], grant_id=grant_id)
    return {"status": "deleted", "grant": deleted, "stub": False}


async def patch_collection_default_acl(
    tenant_id: str,
    collection_id: str,
    request: Request,
) -> dict[str, Any]:
    body = await request.json()
    default_acl = body.get("default_acl")
    if not isinstance(default_acl, list):
        raise HTTPException(status_code=422, detail={"code": "validation"})
    row = get_acl_store().set_collection_default_acl(
        tenant_id=tenant_id,
        collection_id=collection_id,
        default_acl=[str(p) for p in default_acl],
    )
    publish_acl_changed(tenant_id=tenant_id)
    return {"status": "updated", "collection": row, "stub": False}
