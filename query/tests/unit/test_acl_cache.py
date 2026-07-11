"""ACL in-process cache helpers."""

from __future__ import annotations

from app.acl_cache import flush_acl_cache, get_acl_entry, set_acl_entry


def test_acl_epoch_invalidates_entries() -> None:
    set_acl_entry(tenant_id="acme", principal="user:bob", value={"ok": True})
    assert get_acl_entry(tenant_id="acme", principal="user:bob") is not None
    flush_acl_cache("acme")
    assert get_acl_entry(tenant_id="acme", principal="user:bob") is None
