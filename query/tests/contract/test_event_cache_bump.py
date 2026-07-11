"""Domain event cache invalidation."""

from __future__ import annotations

import os

from app.acl_cache import flush_acl_cache, get_acl_entry, set_acl_entry
from app.event_subscriber import handle_event
from app.query_cache import (
    bump_cache_version,
    cache_key,
    clear_memory_cache,
    get_cache_version,
    get_cached_answer,
    set_cached_answer,
)


def test_acl_changed_flushes_acl_cache() -> None:
    set_acl_entry(tenant_id="acme", principal="user:alice", value={"grants": []})
    assert get_acl_entry(tenant_id="acme", principal="user:alice") is not None
    handle_event({"type": "acl.changed", "tenant_id": "acme"})
    assert get_acl_entry(tenant_id="acme", principal="user:alice") is None


def test_ingest_completed_bumps_cache_version() -> None:
    os.environ["QUERY_CACHE_ENABLED"] = "true"
    os.environ["REDIS_STUB"] = "true"
    clear_memory_cache()
    state = {"tenant_id": "acme", "collection_id": "docs", "query": "policy"}
    payload = {"answer_text": "cached", "sources": []}
    set_cached_answer(state, payload)
    assert get_cached_answer(state) == payload
    handle_event(
        {
            "event": "ingest.completed",
            "tenant_id": "acme",
            "collection_id": "docs",
            "cache_bump": True,
        }
    )
    assert get_cache_version("acme", "docs") == 1
    assert get_cached_answer(state) is None
