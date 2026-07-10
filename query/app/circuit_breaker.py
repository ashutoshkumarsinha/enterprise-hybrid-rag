"""Lightweight circuit breaker for store and inference clients — FR-28 · §18.15."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field


class CircuitOpenError(Exception):
    """Breaker is open; caller should use the degrade path."""

    def __init__(self, name: str) -> None:
        super().__init__(f"circuit open: {name}")
        self.name = name


@dataclass
class CircuitBreaker:
    """Count failures in *closed* state; open after threshold; half-open probe after timeout."""

    name: str
    failure_threshold: int = 5
    reset_timeout_s: float = 30.0
    _state: str = field(default="closed", init=False)
    _failures: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)

    def allow_request(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if time.monotonic() - self._opened_at >= self.reset_timeout_s:
                self._state = "half_open"
                return True
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        if self._state == "half_open":
            self._state = "open"
            self._opened_at = time.monotonic()
            self._failures = self.failure_threshold
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()

    @property
    def state(self) -> str:
        if self._state == "open" and time.monotonic() - self._opened_at >= self.reset_timeout_s:
            return "half_open"
        return self._state

    def snapshot(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self.state,
            "failures": self._failures,
            "failure_threshold": self.failure_threshold,
            "reset_timeout_s": self.reset_timeout_s,
        }


def breakers_enabled() -> bool:
    raw = os.environ.get("CIRCUIT_BREAKERS_ENABLED", "true")
    return raw.lower() in ("true", "1", "yes", "on")


def run_guarded(breaker: CircuitBreaker, fn):
    """Execute *fn* when the breaker allows; record success/failure."""
    if breakers_enabled() and not breaker.allow_request():
        raise CircuitOpenError(breaker.name)
    try:
        result = fn()
    except Exception:
        if breakers_enabled():
            breaker.record_failure()
        raise
    if breakers_enabled():
        breaker.record_success()
    return result
