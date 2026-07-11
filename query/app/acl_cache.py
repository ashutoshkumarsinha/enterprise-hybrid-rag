"""In-process ACL metadata cache invalidation (spec §18)."""

from __future__ import annotations

from typing import Any

_ACL_EPOCH: dict[str, int] = {}
_ACL_ENTRIES: dict[str, dict[str, Any]] = {}


def acl_cache_key(*, tenant_id: str, principal: str) -> str:
    epoch = _ACL_EPOCH.get(tenant_id, 0)
    return f"{tenant_id}:{epoch}:{principal}"


def get_acl_entry(*, tenant_id: str, principal: str) -> dict[str, Any] | None:
    return _ACL_ENTRIES.get(acl_cache_key(tenant_id=tenant_id, principal=principal))


def set_acl_entry(*, tenant_id: str, principal: str, value: dict[str, Any]) -> None:
    _ACL_ENTRIES[acl_cache_key(tenant_id=tenant_id, principal=principal)] = value


def flush_acl_cache(tenant_id: str | None = None) -> int:
    """Bump ACL epoch for a tenant (or all tenants) and drop cached entries."""
    if tenant_id:
        _ACL_EPOCH[tenant_id] = _ACL_EPOCH.get(tenant_id, 0) + 1
        prefix = f"{tenant_id}:"
        stale = [key for key in _ACL_ENTRIES if key.startswith(prefix)]
        for key in stale:
            _ACL_ENTRIES.pop(key, None)
        return len(stale)
    count = len(_ACL_ENTRIES)
    _ACL_EPOCH.clear()
    _ACL_ENTRIES.clear()
    return count
