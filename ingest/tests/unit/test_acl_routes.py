"""ACL admin HTTP routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.acl_store import reset_acl_store
from app.orchestrator import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("CATALOG_DSN", raising=False)
    reset_acl_store()
    with TestClient(app) as test_client:
        yield test_client
    reset_acl_store()


def test_create_and_list_acl_grant(client: TestClient) -> None:
    response = client.post(
        "/admin/acl/grants",
        json={
            "tenant_id": "acme",
            "principal": "group:payments-team",
            "collection_id": "payments-api",
            "permission": "read",
        },
    )
    assert response.status_code == 200
    grant_id = response.json()["grant"]["grant_id"]

    listed = client.get("/admin/acl/grants", params={"tenant_id": "acme"})
    assert listed.status_code == 200
    ids = {g["grant_id"] for g in listed.json()["grants"]}
    assert grant_id in ids


def test_delete_acl_grant(client: TestClient) -> None:
    created = client.post(
        "/admin/acl/grants",
        json={
            "tenant_id": "acme",
            "principal": "user:bob",
            "collection_id": "payments-api",
        },
    )
    grant_id = created.json()["grant"]["grant_id"]
    deleted = client.delete(f"/admin/acl/grants/{grant_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


def test_patch_default_acl(client: TestClient) -> None:
    response = client.patch(
        "/admin/collections/acme/payments-api/default_acl",
        json={"default_acl": ["group:payments-team"]},
    )
    assert response.status_code == 200
    assert response.json()["collection"]["default_acl"] == ["group:payments-team"]
