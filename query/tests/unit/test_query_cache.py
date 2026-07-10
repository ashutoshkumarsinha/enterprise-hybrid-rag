"""Query cache helpers."""

from __future__ import annotations

import os

from app.query_cache import cache_key, clear_memory_cache, get_cached_answer, redis_healthcheck, set_cached_answer


def test_cache_roundtrip_in_stub_mode() -> None:
    os.environ["QUERY_CACHE_ENABLED"] = "true"
    os.environ["REDIS_STUB"] = "true"
    clear_memory_cache()
    state = {
        "tenant_id": "acme",
        "collection_id": "docs",
        "query": "rotation policy",
    }
    payload = {"answer_text": "Rotate keys.", "sources": [], "stub": True}
    set_cached_answer(state, payload)
    cached = get_cached_answer(state)
    assert cached == payload


def test_cache_key_stable() -> None:
    state = {"tenant_id": "a", "collection_id": "b", "query": "q"}
    assert cache_key(state) == cache_key(state)


def test_redis_healthcheck_stub_mode() -> None:
    os.environ["REDIS_STUB"] = "true"
    assert redis_healthcheck() is True
