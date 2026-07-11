"""HTTP 429 admission contract for research routes."""

from __future__ import annotations

import pytest

from app.quota_store import reset_quota_store
from app.rate_limit import reset_rate_limiter


@pytest.fixture(autouse=True)
def _tight_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_STUB", "true")
    monkeypatch.setenv("TENANT_QUERIES_PER_MINUTE", "1")
    monkeypatch.setenv("USER_QUERIES_PER_MINUTE", "1")
    reset_rate_limiter()
    reset_quota_store()


def test_research_documents_returns_429_when_rate_limited(client) -> None:
    first = client.post("/mcp/tools/research_documents", json={"query": "first"})
    assert first.status_code == 200
    second = client.post("/mcp/tools/research_documents", json={"query": "second"})
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "rate_limited"
    assert "Retry-After" in second.headers
    assert "X-RateLimit-Limit" in second.headers


def test_research_stream_returns_429_when_rate_limited(client) -> None:
    first = client.post("/research/stream", json={"query": "first"})
    assert first.status_code == 200
    second = client.post("/research/stream", json={"query": "second"})
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "rate_limited"
