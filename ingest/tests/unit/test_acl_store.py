"""ACL store unit tests."""

from __future__ import annotations

import pytest

from app.acl_store import InMemoryAclStore


@pytest.fixture
def store() -> InMemoryAclStore:
    return InMemoryAclStore()


def test_list_seed_grant(store: InMemoryAclStore) -> None:
    grants = store.list_grants(tenant_id="acme", collection_id="internal-only")
    assert len(grants) == 1
    assert grants[0]["principal"] == "user:alice"


def test_create_and_delete_grant(store: InMemoryAclStore) -> None:
    grant = store.create_grant(
        tenant_id="acme",
        principal="group:payments-team",
        collection_id="payments-api",
        permission="read",
    )
    assert grant["grant_id"]
    listed = store.list_grants(tenant_id="acme", principal="group:payments-team")
    assert len(listed) == 1
    deleted = store.delete_grant(grant["grant_id"])
    assert deleted is not None
    assert store.list_grants(tenant_id="acme", principal="group:payments-team") == []


def test_create_requires_scope(store: InMemoryAclStore) -> None:
    with pytest.raises(ValueError):
        store.create_grant(tenant_id="acme", principal="user:bob")


def test_set_collection_default_acl(store: InMemoryAclStore) -> None:
    row = store.set_collection_default_acl(
        tenant_id="acme",
        collection_id="payments-api",
        default_acl=["group:payments-team"],
    )
    assert row["default_acl"] == ["group:payments-team"]
