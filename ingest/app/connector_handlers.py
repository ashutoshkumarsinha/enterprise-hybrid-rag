"""Connector sync HTTP handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.tasks import connector_sync


async def enqueue_collection_sync(request: Request) -> dict[str, Any]:
    body = await request.json()
    tenant_id = body.get("tenant_id")
    collection_id = body.get("collection_id")
    if not tenant_id or not collection_id:
        raise HTTPException(status_code=422, detail={"code": "validation"})
    payload = {
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "version_id": body.get("version_id", "v1"),
        "mode": body.get("mode", "incremental"),
        "connector": body.get("connector", "s3"),
        "prefix": body.get("prefix"),
        "since": body.get("since"),
        "parser_profile": body.get("parser_profile"),
    }
    async_result = connector_sync.delay(payload)
    return {
        "status": "accepted",
        "task_id": async_result.id,
        "connector": payload["connector"],
        "mode": payload["mode"],
        "stub": False,
    }
