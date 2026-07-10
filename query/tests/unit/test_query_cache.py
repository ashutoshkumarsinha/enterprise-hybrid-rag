"""Query result cache in-memory mode."""

from __future__ import annotations

import os

from app.query_cache import cache_key, clear_memory_cache, get_cached_answer, set_cached_answer


def test_query_cache_roundtrip() -> None:
    os.environ["QUERY_CACHE_ENABLED"] = "true"
    os.environ["REDIS_STUB"] = "true"
    clear_memory_cache()
    state = {"tenant_id": "t", "collection_id": "c", "query": "hello"}
    key = cache_key(state)
    assert key.startswith("qcache:")
    set_cached_answer(state, {"answer_text": "cached", "sources": [], "stub": False})
    hit = get_cached_answer(state)
    assert hit is not None
    assert hit["answer_text"] == "cached"
