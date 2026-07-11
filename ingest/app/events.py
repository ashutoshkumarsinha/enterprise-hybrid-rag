"""Publish ingest catalog events for query cache invalidation."""

from __future__ import annotations

import json
import os


def publish_acl_changed(*, tenant_id: str, grant_id: str | None = None) -> None:
    """Emit ``acl.changed`` on the Redis events stream (best-effort)."""
    url = os.environ.get("REDIS_URL")
    if not url:
        return
    stream = os.environ.get("REDIS_EVENTS_STREAM", "rag:events")
    payload = {
        "type": "acl.changed",
        "tenant_id": tenant_id,
        "grant_id": grant_id,
    }
    try:
        import redis

        client = redis.from_url(url)
        client.xadd(stream, {"payload": json.dumps(payload)})
    except Exception:
        return
