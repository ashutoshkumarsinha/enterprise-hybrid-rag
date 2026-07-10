"""Circuit breaker behavior."""

from __future__ import annotations

import os

import pytest

from app.circuit_breaker import CircuitBreaker, CircuitOpenError, run_guarded
from app.client_factory import get_breakers, reset_clients


def test_opens_after_failure_threshold() -> None:
    breaker = CircuitBreaker("test", failure_threshold=3, reset_timeout_s=60.0)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            run_guarded(breaker, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert breaker.state == "open"
    with pytest.raises(CircuitOpenError):
        run_guarded(breaker, lambda: "ok")


def test_success_resets_failures() -> None:
    breaker = CircuitBreaker("test", failure_threshold=3, reset_timeout_s=60.0)
    with pytest.raises(RuntimeError):
        run_guarded(breaker, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert run_guarded(breaker, lambda: "ok") == "ok"
    assert breaker.state == "closed"


def test_registry_has_expected_clients() -> None:
    reset_clients()
    os.environ["CIRCUIT_BREAKERS_ENABLED"] = "true"
    names = set(get_breakers())
    assert {"embed", "chat", "qdrant", "neo4j", "reranker"} <= names
