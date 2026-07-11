"""In-process operational counters for query (HPA / observability hooks)."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

_lock = Lock()
_counters: dict[str, int] = defaultdict(int)

_METRIC_RATE_LIMIT_REJECTED = "rate_limit_rejected_total"


def _counter_key(name: str, *, labels: dict[str, str] | None = None) -> str:
    if not labels:
        return name
    parts = "|".join(f"{key}={labels[key]}" for key in sorted(labels))
    return f"{name}|{parts}"


def inc_counter(name: str, *, labels: dict[str, str] | None = None, amount: int = 1) -> None:
    key = _counter_key(name, labels=labels)
    with _lock:
        _counters[key] += amount


def snapshot_counters() -> dict[str, int]:
    with _lock:
        return dict(_counters)


def rate_limit_rejected_total() -> int:
    with _lock:
        return int(_counters.get(_METRIC_RATE_LIMIT_REJECTED, 0))


def metrics_snapshot() -> dict[str, int | dict[str, int]]:
    with _lock:
        total = int(_counters.get(_METRIC_RATE_LIMIT_REJECTED, 0))
        by_kind: dict[str, int] = {}
        prefix = f"{_METRIC_RATE_LIMIT_REJECTED}|"
        for key, value in _counters.items():
            if not key.startswith(prefix):
                continue
            kind = key.split("kind=", 1)[-1]
            by_kind[kind] = int(value)
    return {
        "rate_limit_rejected_total": total,
        "rate_limit_rejected_by_kind": by_kind,
    }


def record_rate_limit_rejected(*, kind: str, tenant_id: str) -> None:
    del tenant_id  # reserved for future sampled labels; avoid cardinality in v1
    inc_counter(_METRIC_RATE_LIMIT_REJECTED, amount=1)
    inc_counter(_METRIC_RATE_LIMIT_REJECTED, labels={"kind": kind}, amount=1)


def reset_metrics() -> None:
    with _lock:
        _counters.clear()
