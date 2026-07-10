"""MCP catalog tool handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.auth import enforce_tenant_binding
from app.catalog_store import CatalogStore, format_documents_markdown
from app.client_factory import get_neo4j_client
from app.models import AuthContext
from app.rbac import require_tool
from app.settings import Settings, get_settings


def _tenant_id(ctx: AuthContext, args: dict[str, Any]) -> str:
    return args.get("tenant_id") or ctx.tenant_id


def handle_list_indexed_documents(
    args: dict[str, Any],
    *,
    ctx: AuthContext,
    catalog_store: CatalogStore,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    require_tool(ctx, "list_indexed_documents", settings=settings)
    enforce_tenant_binding(ctx, args, settings=settings)
    tenant_id = _tenant_id(ctx, args)
    documents, next_cursor = catalog_store.list_indexed_documents(
        tenant_id=tenant_id,
        principal=ctx.principal,
        collection_id=args.get("collection_id"),
        document_id=args.get("document_id"),
        limit=min(int(args.get("limit", 50)), 500),
        cursor=args.get("cursor"),
    )
    return {
        "markdown": format_documents_markdown(documents),
        "count": len(documents),
        "next_cursor": next_cursor,
    }


def handle_get_document_metadata(
    args: dict[str, Any],
    *,
    ctx: AuthContext,
    catalog_store: CatalogStore,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    require_tool(ctx, "get_document_metadata", settings=settings)
    enforce_tenant_binding(ctx, args, settings=settings)
    document_id = args.get("document_id")
    if not document_id:
        raise HTTPException(status_code=422, detail={"code": "validation", "message": "document_id"})
    row = catalog_store.get_document_metadata(
        tenant_id=_tenant_id(ctx, args),
        principal=ctx.principal,
        document_id=document_id,
        collection_id=args.get("collection_id"),
        version_id=args.get("version_id"),
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": document_id})
    return {
        "document_id": row["document_id"],
        "collection_id": row["collection_id"],
        "title": row.get("title"),
        "version_id": row.get("version_id") or row.get("latest_version_id"),
        "chunk_count": row.get("chunk_count", 0),
        "ingested_at": row.get("ingested_at"),
        "source_uri": row.get("source_uri"),
        "source_system": row.get("source_system"),
        "tags": row.get("tags") or [],
        "acl": row.get("acl", {}),
    }


def handle_visualize_document_graph(
    args: dict[str, Any],
    *,
    ctx: AuthContext,
    catalog_store: CatalogStore,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    require_tool(ctx, "visualize_document_graph", settings=settings)
    enforce_tenant_binding(ctx, args, settings=settings)
    document_id = args.get("document_id")
    if not document_id:
        raise HTTPException(status_code=422, detail={"code": "validation", "message": "document_id"})
    tenant_id = _tenant_id(ctx, args)
    row = catalog_store.get_document_metadata(
        tenant_id=tenant_id,
        principal=ctx.principal,
        document_id=document_id,
        collection_id=args.get("collection_id"),
        version_id=args.get("version_id"),
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": document_id})
    neo4j = get_neo4j_client()
    mermaid = neo4j.document_graph_mermaid(
        tenant_id=tenant_id,
        collection_id=row["collection_id"],
        document_id=document_id,
        depth=min(int(args.get("depth", 2)), 5),
    )
    return {"format": args.get("format", "mermaid"), "mermaid": mermaid}
