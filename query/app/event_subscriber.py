"""Redis Stream subscriber for ingest domain events (IF-3)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from app.acl_cache import flush_acl_cache
from app.query_cache import bump_cache_version

_LAST_EVENT_ID = "$"
_listener_task: asyncio.Task | None = None


def _events_enabled() -> bool:
    if os.environ.get("QUERY_EVENTS_ENABLED", "").lower() in ("false", "0", "no"):
        return False
    if os.environ.get("REDIS_STUB", "").lower() in ("true", "1", "yes"):
        return False
    return bool(os.environ.get("REDIS_URL"))


def _stream_name() -> str:
    return os.environ.get("REDIS_EVENTS_STREAM", "rag:events")


def handle_event(payload: dict[str, Any]) -> None:
    """Dispatch a single domain event payload."""
    event_type = payload.get("event") or payload.get("type")
    tenant_id = payload.get("tenant_id")
    if not event_type:
        return
    if event_type == "acl.changed":
        if tenant_id:
            flush_acl_cache(tenant_id)
        else:
            flush_acl_cache()
        return
    if event_type in ("ingest.completed", "connector.sync"):
        if tenant_id and payload.get("cache_bump", True):
            bump_cache_version(tenant_id, payload.get("collection_id"))


def process_events_once(*, block_ms: int = 0) -> int:
    """Read and handle pending events from the Redis stream."""
    global _LAST_EVENT_ID
    if not _events_enabled():
        return 0
    try:
        import redis

        client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        rows = client.xread({_stream_name(): _LAST_EVENT_ID}, count=32, block=block_ms)
    except Exception:
        return 0
    handled = 0
    for _stream, messages in rows or []:
        for message_id, fields in messages:
            _LAST_EVENT_ID = message_id
            raw = fields.get("payload") or fields.get("data")
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            handle_event(payload)
            handled += 1
    return handled


async def _event_loop() -> None:
    while True:
        process_events_once(block_ms=1000)
        await asyncio.sleep(0)


def start_event_subscriber() -> asyncio.Task | None:
    global _listener_task
    if not _events_enabled() or _listener_task is not None:
        return _listener_task
    _listener_task = asyncio.create_task(_event_loop())
    return _listener_task


async def stop_event_subscriber() -> None:
    global _listener_task
    if _listener_task is None:
        return
    _listener_task.cancel()
    try:
        await _listener_task
    except asyncio.CancelledError:
        pass
    _listener_task = None
