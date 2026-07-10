"""Shared pytest fixtures for hybrid-rag-query."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.catalog_store import create_catalog_store
from app.mcp_server import app
from app.session_store import InMemorySessionStore
from app.settings import get_settings
from app.token_store import InMemoryTokenStore


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live stack tests (requires LIVE_STACK=1)",
    )


@pytest.fixture()
def client() -> TestClient:
    settings = get_settings()
    app.state.settings = settings
    app.state.token_store = InMemoryTokenStore()
    app.state.session_store = InMemorySessionStore()
    app.state.catalog_store = create_catalog_store(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    response = client.post(
        "/admin/mcp/tokens",
        json={
            "tenant_id": "acme",
            "principal": "user:alice",
            "role_template": "admin",
            "label": "test",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]
