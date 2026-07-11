"""Operational metrics counters."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.metrics import (
    metrics_snapshot,
    rate_limit_rejected_total,
    record_rate_limit_rejected,
    reset_metrics,
)
from app.models import AuthContext
from app.quota_store import reset_quota_store
from app.rate_limit import assert_query_admission, reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_STUB", "true")
    monkeypatch.setenv("TENANT_QUERIES_PER_MINUTE", "1")
    monkeypatch.setenv("USER_QUERIES_PER_MINUTE", "1")
    reset_metrics()
    reset_rate_limiter()
    reset_quota_store()


def test_record_rate_limit_rejected_increments_total() -> None:
    record_rate_limit_rejected(kind="queries_per_minute", tenant_id="acme")
    assert rate_limit_rejected_total() == 1
    snapshot = metrics_snapshot()
    assert snapshot["rate_limit_rejected_total"] == 1
    assert snapshot["rate_limit_rejected_by_kind"]["queries_per_minute"] == 1


def test_assert_query_admission_records_rejection() -> None:
    ctx = AuthContext(
        tenant_id="acme",
        principal="user:alice",
        permissions=["mcp.research"],
        auth_method="dev_bypass",
    )
    assert_query_admission(ctx)
    with pytest.raises(HTTPException):
        assert_query_admission(ctx)
    assert rate_limit_rejected_total() == 1


def test_admin_metrics_endpoint(client) -> None:
    response = client.get("/admin/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["module"] == "hybrid-rag-query"
    assert "rate_limit_rejected_total" in body["metrics"]


def test_healthz_includes_metrics(client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "metrics" in response.json()
