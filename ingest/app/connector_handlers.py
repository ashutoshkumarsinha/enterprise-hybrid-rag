"""Connector sync HTTP handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.connector_enqueue import enqueue_connector_sync


async def enqueue_collection_sync(request: Request) -> dict[str, Any]:
    body = await request.json()
    try:
        return enqueue_connector_sync(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "validation", "message": str(exc)}) from exc
