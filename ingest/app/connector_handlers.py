"""Connector sync HTTP handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.job_store import get_job_store
from app.tasks import connector_sync


async def enqueue_collection_sync(request: Request) -> dict[str, Any]:
    body = await request.json()
    tenant_id = body.get("tenant_id")
    collection_id = body.get("collection_id")
    if not tenant_id or not collection_id:
        raise HTTPException(status_code=422, detail={"code": "validation"})
    mode = body.get("mode", "incremental")
    job = get_job_store().create_job(
        tenant_id=tenant_id,
        collection_id=collection_id,
        mode=mode,
        job_type="connector_sync",
        metadata={
            "connector": body.get("connector", "s3"),
            "version_id": body.get("version_id", "v1"),
        },
    )
    payload = {
        "job_id": job["job_id"],
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "version_id": body.get("version_id", "v1"),
        "mode": mode,
        "connector": body.get("connector", "s3"),
        "prefix": body.get("prefix"),
        "since": body.get("since"),
        "parser_profile": body.get("parser_profile"),
    }
    async_result = connector_sync.delay(payload)
    return {
        "status": "accepted",
        "job_id": job["job_id"],
        "task_id": async_result.id,
        "connector": payload["connector"],
        "mode": payload["mode"],
        "stub": False,
    }
