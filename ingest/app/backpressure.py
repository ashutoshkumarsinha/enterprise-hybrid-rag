"""Celery queue depth backpressure — FR-29."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException


@dataclass(frozen=True)
class BackpressureStatus:
    queue_depth: int
    warn: bool
    paused: bool
    enabled: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "queue_depth": self.queue_depth,
            "warn": self.warn,
            "paused": self.paused,
        }


def backpressure_enabled() -> bool:
    return os.environ.get("INGEST_BACKPRESSURE_ENABLED", "true").lower() in ("true", "1", "yes")


def warn_depth() -> int:
    return int(os.environ.get("INGEST_BACKPRESSURE_WARN_DEPTH", "100"))


def pause_depth() -> int:
    return int(os.environ.get("INGEST_BACKPRESSURE_PAUSE_DEPTH", "1000"))


def queue_name() -> str:
    return os.environ.get("CELERY_QUEUE_NAME", "celery")


def _redis_queue_depth(broker_url: str) -> int:
    parsed = urlparse(broker_url)
    if parsed.scheme not in ("redis", "rediss"):
        return 0
    import redis

    db = int((parsed.path or "/0").lstrip("/") or "0")
    client = redis.from_url(broker_url)
    try:
        return int(client.llen(queue_name()))
    except Exception:
        return 0
    finally:
        client.close()


def get_queue_depth() -> int:
    if os.environ.get("INGEST_BACKPRESSURE_STUB", "").lower() in ("true", "1", "yes"):
        return int(os.environ.get("INGEST_BACKPRESSURE_STUB_DEPTH", "0"))
    broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")
    return _redis_queue_depth(broker)


def check_backpressure() -> BackpressureStatus:
    if not backpressure_enabled():
        return BackpressureStatus(queue_depth=0, warn=False, paused=False, enabled=False)
    depth = get_queue_depth()
    return BackpressureStatus(
        queue_depth=depth,
        warn=depth >= warn_depth(),
        paused=depth >= pause_depth(),
        enabled=True,
    )


def assert_enqueue_allowed() -> BackpressureStatus:
    """Raise HTTP 503 when queue depth exceeds pause threshold."""
    status = check_backpressure()
    if status.paused:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "backpressure",
                "message": "ingest enqueue paused — celery queue depth exceeded",
                "queue_depth": status.queue_depth,
                "pause_depth": pause_depth(),
            },
        )
    return status
