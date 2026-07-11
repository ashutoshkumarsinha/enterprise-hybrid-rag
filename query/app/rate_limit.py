"""Query admission + rate limits — FR-27, FR-30."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException

from app.models import AuthContext
from app.quota_store import get_quota_store


@dataclass(frozen=True)
class AdmissionResult:
    allowed: bool
    retry_after_s: int
    tenant_remaining: int
    user_remaining: int
    headers: dict[str, str]


def rate_limit_enabled() -> bool:
    return os.environ.get("QUERY_RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")


def user_queries_per_minute() -> int:
    return int(os.environ.get("USER_QUERIES_PER_MINUTE", "30"))


def user_max_concurrent_streams() -> int:
    return int(os.environ.get("MAX_CONCURRENT_STREAMS_PER_USER", "3"))


class _InMemoryLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._streams: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def _prune(self, key: str, *, window_s: float = 60.0) -> deque[float]:
        now = time.monotonic()
        bucket = self._events[key]
        while bucket and now - bucket[0] > window_s:
            bucket.popleft()
        return bucket

    def check_query(self, *, tenant_id: str, principal: str, tenant_limit: int, user_limit: int) -> AdmissionResult:
        with self._lock:
            tenant_key = f"tenant:{tenant_id}"
            user_key = f"user:{tenant_id}:{principal}"
            tenant_bucket = self._prune(tenant_key)
            user_bucket = self._prune(user_key)
            if len(tenant_bucket) >= tenant_limit or len(user_bucket) >= user_limit:
                retry = 1
                if tenant_bucket:
                    retry = max(1, int(60 - (time.monotonic() - tenant_bucket[0])))
                return AdmissionResult(
                    allowed=False,
                    retry_after_s=retry,
                    tenant_remaining=0,
                    user_remaining=0,
                    headers=_rate_headers(tenant_limit, 0, retry),
                )
            now = time.monotonic()
            tenant_bucket.append(now)
            user_bucket.append(now)
            return AdmissionResult(
                allowed=True,
                retry_after_s=0,
                tenant_remaining=max(tenant_limit - len(tenant_bucket), 0),
                user_remaining=max(user_limit - len(user_bucket), 0),
                headers=_rate_headers(tenant_limit, max(tenant_limit - len(tenant_bucket), 0), 0),
            )

    def acquire_stream(self, *, tenant_id: str, principal: str, tenant_limit: int, user_limit: int) -> None:
        with self._lock:
            tenant_key = f"stream:tenant:{tenant_id}"
            user_key = f"stream:user:{tenant_id}:{principal}"
            if self._streams[tenant_key] >= tenant_limit or self._streams[user_key] >= user_limit:
                raise HTTPException(
                    status_code=429,
                    detail={"code": "rate_limited", "kind": "concurrent_streams"},
                    headers={"Retry-After": "1"},
                )
            self._streams[tenant_key] += 1
            self._streams[user_key] += 1

    def release_stream(self, *, tenant_id: str, principal: str) -> None:
        with self._lock:
            tenant_key = f"stream:tenant:{tenant_id}"
            user_key = f"stream:user:{tenant_id}:{principal}"
            self._streams[tenant_key] = max(self._streams[tenant_key] - 1, 0)
            self._streams[user_key] = max(self._streams[user_key] - 1, 0)


class _RedisLimiter:
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.from_url(url, decode_responses=True)

    def check_query(self, *, tenant_id: str, principal: str, tenant_limit: int, user_limit: int) -> AdmissionResult:
        tenant_key = f"rlimit:{tenant_id}:queries"
        user_key = f"rlimit:{tenant_id}:{principal}:queries"
        tenant_count = int(self._client.incr(tenant_key))
        if tenant_count == 1:
            self._client.expire(tenant_key, 60)
        user_count = int(self._client.incr(user_key))
        if user_count == 1:
            self._client.expire(user_key, 60)
        if tenant_count > tenant_limit or user_count > user_limit:
            self._client.decr(tenant_key)
            self._client.decr(user_key)
            ttl = int(self._client.ttl(tenant_key) or 1)
            return AdmissionResult(
                allowed=False,
                retry_after_s=max(ttl, 1),
                tenant_remaining=0,
                user_remaining=0,
                headers=_rate_headers(tenant_limit, 0, max(ttl, 1)),
            )
        return AdmissionResult(
            allowed=True,
            retry_after_s=0,
            tenant_remaining=max(tenant_limit - tenant_count, 0),
            user_remaining=max(user_limit - user_count, 0),
            headers=_rate_headers(tenant_limit, max(tenant_limit - tenant_count, 0), 0),
        )

    def acquire_stream(self, *, tenant_id: str, principal: str, tenant_limit: int, user_limit: int) -> None:
        tenant_key = f"rlimit:{tenant_id}:streams"
        user_key = f"rlimit:{tenant_id}:{principal}:streams"
        tenant_count = int(self._client.incr(tenant_key))
        user_count = int(self._client.incr(user_key))
        if tenant_count > tenant_limit or user_count > user_limit:
            self._client.decr(tenant_key)
            self._client.decr(user_key)
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "kind": "concurrent_streams"},
                headers={"Retry-After": "1"},
            )

    def release_stream(self, *, tenant_id: str, principal: str) -> None:
        tenant_key = f"rlimit:{tenant_id}:streams"
        user_key = f"rlimit:{tenant_id}:{principal}:streams"
        self._client.decr(tenant_key)
        self._client.decr(user_key)


_limiter: _InMemoryLimiter | _RedisLimiter | None = None


def _rate_headers(limit: int, remaining: int, retry_after: int) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
    }
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return headers


def get_limiter() -> _InMemoryLimiter | _RedisLimiter:
    global _limiter
    if _limiter is None:
        if os.environ.get("REDIS_STUB", "true").lower() in ("true", "1", "yes"):
            _limiter = _InMemoryLimiter()
        else:
            url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
            _limiter = _RedisLimiter(url)
    return _limiter


def reset_rate_limiter() -> None:
    global _limiter
    _limiter = None


def assert_query_admission(ctx: AuthContext) -> AdmissionResult:
    """Check per-tenant and per-user query rate limits before pipeline entry."""
    if not rate_limit_enabled():
        return AdmissionResult(True, 0, 999, 999, {})
    limits = get_quota_store().get_limits(ctx.tenant_id)
    result = get_limiter().check_query(
        tenant_id=ctx.tenant_id,
        principal=ctx.principal,
        tenant_limit=limits.queries_per_minute,
        user_limit=user_queries_per_minute(),
    )
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "kind": "queries_per_minute",
                "tenant_id": ctx.tenant_id,
            },
            headers=result.headers,
        )
    return result


def acquire_stream_slot(ctx: AuthContext) -> None:
    if not rate_limit_enabled():
        return
    limits = get_quota_store().get_limits(ctx.tenant_id)
    get_limiter().acquire_stream(
        tenant_id=ctx.tenant_id,
        principal=ctx.principal,
        tenant_limit=limits.max_concurrent_streams,
        user_limit=user_max_concurrent_streams(),
    )


def release_stream_slot(ctx: AuthContext) -> None:
    if not rate_limit_enabled():
        return
    get_limiter().release_stream(tenant_id=ctx.tenant_id, principal=ctx.principal)
