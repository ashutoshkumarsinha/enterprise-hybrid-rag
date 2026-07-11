"""Live-stack integration tests for ingest writes."""

from __future__ import annotations

import os

import pytest


def live_stack_requested() -> bool:
    return os.environ.get("LIVE_STACK", "").lower() in ("1", "true", "yes")


def live_stack_strict() -> bool:
    return os.environ.get("LIVE_STACK_STRICT", "").lower() in ("1", "true", "yes")


def skip_or_fail(message: str) -> None:
    if live_stack_strict():
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="session", autouse=True)
def require_live_stack() -> None:
    if not live_stack_requested():
        pytest.skip("Set LIVE_STACK=1 to run ingest integration tests")


def _clients_using_stubs() -> list[str]:
    from app.clients.embed import EmbedClient
    from app.clients.qdrant import QdrantWriter

    stubs: list[str] = []
    if EmbedClient().is_stub:
        stubs.append("embed")
    if QdrantWriter().is_stub:
        stubs.append("qdrant")
    return stubs


@pytest.fixture(scope="session")
def ingest_live_ready(require_live_stack: None) -> None:
    os.environ.setdefault("INGEST_WRITE_STUB", "false")
    os.environ.setdefault("DEDUP_ENABLED", "false")
    stubs = _clients_using_stubs()
    if stubs:
        skip_or_fail(
            "Ingest live stack requested but clients in stub mode: "
            + ", ".join(stubs)
            + " (see ingest/.env.live.example)"
        )
    from app.clients.embed import EmbedClient
    from app.clients.qdrant import QdrantWriter

    if not QdrantWriter().healthcheck():
        skip_or_fail("Qdrant unhealthy for ingest integration")
    if not EmbedClient().healthcheck():
        skip_or_fail("Embed service unhealthy for ingest integration")
