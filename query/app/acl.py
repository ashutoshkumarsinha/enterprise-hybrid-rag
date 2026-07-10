"""ACL evaluation for catalog reads — FR-03 deny-by-default on secured collections."""

from __future__ import annotations

from typing import Any

from app.models import AuthContext


def principals_for_acl(ctx: AuthContext) -> set[str]:
    """Principal set used for ``acl_grants`` lookup."""
    principals = {ctx.principal}
    if ctx.principal.startswith("user:"):
        principals.add(ctx.principal.removeprefix("user:"))
    return principals


def collection_is_secured(default_acl: list[Any], grants: list[dict[str, Any]]) -> bool:
    return bool(default_acl) or bool(grants)


def can_read_document(
    principals: set[str],
    *,
    collection_id: str,
    document_id: str,
    default_acl: list[Any],
    grants: list[dict[str, Any]],
) -> bool:
    """Return whether *principals* may read *document_id* in *collection_id*."""
    collection_grants = [g for g in grants if g.get("collection_id") == collection_id]
    if not collection_is_secured(default_acl, collection_grants):
        return True

    if any(p in default_acl for p in principals):
        return True

    for grant in collection_grants:
        grant_principal = grant.get("principal")
        if grant_principal not in principals:
            continue
        grant_doc = grant.get("document_id")
        if grant_doc is None or grant_doc == document_id:
            return True

    return False
