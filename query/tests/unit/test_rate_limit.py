"""Query admission and rate limits — FR-27, FR-30."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models import AuthContext
from app.metrics import reset_metrics
from app.quota_store import InMemoryQuotaStore, reset_quota_store
from app.rate_limit import (
    _InMemoryLimiter,
    acquire_stream_slot,
    assert_query_admission,
    release_stream_slot,
    reset_rate_limiter,
)


@pytest.fixture(autouse=True)
def _reset_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_STUB", "true")
    monkeypatch.setenv("TENANT_QUERIES_PER_MINUTE", "2")
    monkeypatch.setenv("USER_QUERIES_PER_MINUTE", "2")
    monkeypatch.setenv("MAX_CONCURRENT_STREAMS_PER_USER", "1")
    monkeypatch.setenv("MAX_CONCURRENT_STREAMS_PER_TENANT", "2")
    reset_rate_limiter()
    reset_quota_store()
    reset_metrics()


def _ctx(tenant: str = "acme", principal: str = "user:alice") -> AuthContext:
    return AuthContext(
        tenant_id=tenant,
        principal=principal,
        permissions=["mcp.research"],
        auth_method="dev_bypass",
    )


def test_query_admission_allows_under_limit() -> None:
    assert_query_admission(_ctx())
    assert_query_admission(_ctx())


def test_query_admission_rejects_over_limit() -> None:
    assert_query_admission(_ctx())
    assert_query_admission(_ctx())
    with pytest.raises(HTTPException) as exc:
        assert_query_admission(_ctx())
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "rate_limited"
    assert "Retry-After" in exc.value.headers


def test_tenant_quota_override(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryQuotaStore()
    store.set_limits("acme", query_qps=1 / 60, max_concurrent_streams=1)
    monkeypatch.setattr("app.rate_limit.get_quota_store", lambda: store)
    assert_query_admission(_ctx())
    with pytest.raises(HTTPException):
        assert_query_admission(_ctx())


def test_stream_slot_acquire_and_release() -> None:
    acquire_stream_slot(_ctx())
    with pytest.raises(HTTPException) as exc:
        acquire_stream_slot(_ctx())
    assert exc.value.status_code == 429
    assert exc.value.detail["kind"] == "concurrent_streams"
    release_stream_slot(_ctx())
    acquire_stream_slot(_ctx())
    release_stream_slot(_ctx())


def test_in_memory_limiter_prunes_old_events() -> None:
    limiter = _InMemoryLimiter()
    result = limiter.check_query(
        tenant_id="t1",
        principal="u1",
        tenant_limit=1,
        user_limit=1,
    )
    assert result.allowed
    blocked = limiter.check_query(
        tenant_id="t1",
        principal="u1",
        tenant_limit=1,
        user_limit=1,
    )
    assert not blocked.allowed
    limiter._events["tenant:t1"].clear()
    limiter._events["user:t1:u1"].clear()
    allowed = limiter.check_query(
        tenant_id="t1",
        principal="u1",
        tenant_limit=1,
        user_limit=1,
    )
    assert allowed.allowed
