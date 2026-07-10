"""Fixtures for live-stack integration tests (§13.4 · docs/TESTING.md)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.client_factory import reset_clients
from app.mcp_server import app
from app.session_store import InMemorySessionStore
from app.settings import get_settings
from app.token_store import InMemoryTokenStore


def live_stack_requested() -> bool:
    return os.environ.get("LIVE_STACK", "").lower() in ("1", "true", "yes")


def live_stack_strict() -> bool:
    return os.environ.get("LIVE_STACK_STRICT", "").lower() in ("1", "true", "yes")


def skip_or_fail(message: str) -> None:
    if live_stack_strict():
        pytest.fail(message)
    pytest.skip(message)


def _client_using_stubs() -> list[str]:
    from app.client_factory import (
        get_chat_client,
        get_embed_client,
        get_neo4j_client,
        get_qdrant_client,
        get_reranker_client,
    )

    stubs: list[str] = []
    if get_qdrant_client().is_stub:
        stubs.append("qdrant")
    if get_embed_client().is_stub:
        stubs.append("embed")
    if get_chat_client().is_stub:
        stubs.append("chat")
    if get_reranker_client().is_stub:
        stubs.append("reranker")
    if get_neo4j_client().is_stub:
        stubs.append("neo4j")
    return stubs


def _unhealthy_checks() -> list[str]:
    from app.catalog_store import create_catalog_store
    from app.client_factory import (
        get_chat_client,
        get_embed_client,
        get_neo4j_client,
        get_qdrant_client,
        get_reranker_client,
    )
    from app.query_cache import redis_healthcheck

    settings = get_settings()
    checks: list[str] = []
    if not get_qdrant_client().healthcheck():
        checks.append("qdrant")
    if not get_embed_client().healthcheck():
        checks.append("embed")
    if not get_chat_client().healthcheck():
        checks.append("chat")
    if not get_reranker_client().healthcheck():
        checks.append("reranker")
    if not settings.stub_health and not get_neo4j_client().healthcheck():
        checks.append("neo4j")
    if not settings.stub_health and not redis_healthcheck():
        checks.append("redis")
    if not settings.stub_health and not create_catalog_store(settings).healthcheck():
        checks.append("catalog")
    return checks


@pytest.fixture(scope="session", autouse=True)
def require_live_stack() -> None:
    if not live_stack_requested():
        pytest.skip("Set LIVE_STACK=1 to run integration tests")


@pytest.fixture(scope="session")
def live_stack_ready(require_live_stack: None) -> None:
    """Ensure configured backends respond before running integration cases."""
    reset_clients()
    get_settings.cache_clear()

    stubs = _client_using_stubs()
    if stubs:
        skip_or_fail(
            "Live stack requested but clients still in stub mode: "
            + ", ".join(stubs)
            + " (see query/.env.live.example)"
        )

    unhealthy = _unhealthy_checks()
    if unhealthy:
        skip_or_fail("Live stack backends unhealthy: " + ", ".join(unhealthy))


@pytest.fixture(autouse=True)
def reset_live_clients(live_stack_ready: None) -> Iterator[None]:
    reset_clients()
    get_settings.cache_clear()
    yield
    reset_clients()
    get_settings.cache_clear()


@pytest.fixture()
def live_client() -> Iterator[TestClient]:
    app.state.token_store = InMemoryTokenStore()
    app.state.session_store = InMemorySessionStore()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def prod_health(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force production health gates (STUB_HEALTH=false) for /healthz probes."""
    monkeypatch.setenv("STUB_HEALTH", "false")
    get_settings.cache_clear()
    reset_clients()
    yield
    reset_clients()
    get_settings.cache_clear()
