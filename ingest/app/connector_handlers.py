"""Connector sync HTTP handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.backpressure import assert_enqueue_allowed, check_backpressure
from app.connector_enqueue import enqueue_connector_sync


async def enqueue_collection_sync(request: Request) -> dict[str, Any]:
    body = await request.json()
    bp = assert_enqueue_allowed()
    try:
        result = enqueue_connector_sync(body)
        if bp.warn:
            result["backpressure_warn"] = True
            result["queue_depth"] = bp.queue_depth
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "validation", "message": str(exc)}) from exc
