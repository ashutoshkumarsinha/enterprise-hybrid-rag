"""Production /healthz behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.catalog_store import InMemoryCatalogStore
from app.mcp_server import app
from app.session_store import InMemorySessionStore
from app.settings import get_settings
from app.token_store import InMemoryTokenStore


@pytest.fixture()
def health_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("STUB_HEALTH", "false")
    get_settings.cache_clear()
    settings = get_settings()
    app.state.settings = settings
    app.state.token_store = InMemoryTokenStore()
    app.state.session_store = InMemorySessionStore()
    app.state.catalog_store = InMemoryCatalogStore()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def test_healthz_returns_503_when_qdrant_unhealthy(health_client: TestClient) -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.healthcheck.return_value = False
    mock_embed = MagicMock()
    mock_embed.healthcheck.return_value = True
    mock_chat = MagicMock()
    mock_chat.healthcheck.return_value = True
    mock_reranker = MagicMock()
    mock_reranker.healthcheck.return_value = True

    with (
        patch("app.client_factory.get_qdrant_client", return_value=mock_qdrant),
        patch("app.client_factory.get_embed_client", return_value=mock_embed),
        patch("app.client_factory.get_chat_client", return_value=mock_chat),
        patch("app.client_factory.get_reranker_client", return_value=mock_reranker),
        patch("app.client_factory.get_neo4j_client") as neo4j,
        patch("app.catalog_store.create_catalog_store") as catalog,
        patch("app.query_cache.redis_healthcheck", return_value=True),
    ):
        neo4j.return_value.healthcheck.return_value = True
        catalog.return_value.healthcheck.return_value = True
        response = health_client.get("/healthz")

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["research_ready"] is False
    assert body["checks"]["qdrant_ok"] is False
