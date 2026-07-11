"""Resolve physical Qdrant collection name — E-33 regulated tier."""

from __future__ import annotations

import json
import os
import re

_SUFFIX_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def resolve_qdrant_collection(
    *,
    tenant_id: str,
    base: str | None = None,
    suffix: str | None = None,
) -> str:
    """Return global or per-tenant physical collection name."""
    base_name = base or os.environ.get("QDRANT_COLLECTION", "enterprise_hybrid_rag")
    resolved = suffix if suffix is not None else tenant_suffix(tenant_id)
    if resolved:
        safe = resolved.strip().lower()
        if not _SUFFIX_RE.match(safe):
            raise ValueError(f"invalid qdrant_collection_suffix for tenant {tenant_id!r}")
        return f"{base_name}_{safe}"
    return base_name


def tenant_suffix(tenant_id: str) -> str | None:
    """Lookup suffix from catalog quotas, then env map."""
    try:
        from app.quota_store import get_quota_store

        suffix = get_quota_store().get_qdrant_collection_suffix(tenant_id)
        if suffix:
            return suffix
    except Exception:
        pass
    raw = os.environ.get("QDRANT_TENANT_SUFFIX_JSON", "")
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError:
        return None
    value = mapping.get(tenant_id)
    return str(value).strip() if value else None
