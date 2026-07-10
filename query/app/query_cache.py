"""Redis-backed query result cache — LG-3.

Spec: §6.3.2 result cache · SHARED_CONTRACTS cache keys.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

_CACHE: dict[str, dict[str, Any]] = {}


def _enabled() -> bool:
    return os.environ.get("QUERY_CACHE_ENABLED", "").lower() in ("true", "1", "yes")


def _stub_mode() -> bool:
    return os.environ.get("REDIS_STUB", "").lower() in ("true", "1", "yes") or not os.environ.get(
        "REDIS_URL"
    )


def cache_key(state: dict[str, Any]) -> str:
    parts = [
        state.get("tenant_id", ""),
        state.get("collection_id", ""),
        state.get("document_id") or "",
        state.get("version_id") or "",
        state.get("query", ""),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"qcache:{digest}"


def get_cached_answer(state: dict[str, Any]) -> dict[str, Any] | None:
    if not _enabled():
        return None
    key = cache_key(state)
    if _stub_mode():
        return _CACHE.get(key)
    try:
        import redis

        client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        raw = client.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return _CACHE.get(key)


def set_cached_answer(state: dict[str, Any], payload: dict[str, Any]) -> None:
    if not _enabled():
        return
    key = cache_key(state)
    ttl = int(os.environ.get("QUERY_CACHE_TTL_SECONDS", "3600"))
    if _stub_mode():
        _CACHE[key] = payload
        return
    try:
        import redis

        client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        client.setex(key, ttl, json.dumps(payload))
    except Exception:
        _CACHE[key] = payload


def clear_memory_cache() -> None:
    _CACHE.clear()


def redis_healthcheck() -> bool:
    """Ping Redis when configured; stub mode counts as healthy."""
    if _stub_mode():
        return True
    try:
        import redis

        client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        return bool(client.ping())
    except Exception:
        return False
