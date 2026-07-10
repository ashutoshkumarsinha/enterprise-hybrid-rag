"""Production /healthz gates against live dependencies."""

from __future__ import annotations

import os

import httpx


def test_healthz_prod_gates(live_client, prod_health) -> None:
    response = live_client.get("/healthz")
    body = response.json()
    assert response.status_code == 200, body
    assert body["status"] == "ok"
    assert body["research_ready"] is True
    assert body["stores_ready"] is True
    checks = body["checks"]
    assert checks["qdrant_ok"] is True
    assert checks["inference_ok"] is True
    assert checks["reranker_ok"] is True
    assert checks["redis_ok"] is True
    assert checks["neo4j_ok"] is True
    assert checks["catalog_ok"] is True
    assert "circuit_breakers" in body
    assert set(body["circuit_breakers"]) >= {"embed", "chat", "qdrant", "neo4j", "reranker"}


def test_healthz_running_container_when_configured(live_stack_ready) -> None:
    """Optional: hit a running query container via QUERY_BASE_URL."""
    base = os.environ.get("QUERY_BASE_URL", "").rstrip("/")
    if not base:
        return
    response = httpx.get(f"{base}/healthz", timeout=10.0)
    body = response.json()
    assert response.status_code == 200, body
    assert body.get("research_ready") is True
