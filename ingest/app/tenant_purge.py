"""Tenant offboarding purge — E-21 / spec §9.1."""

from __future__ import annotations

import argparse
import json
import sys

from app.catalog_store import get_catalog_store
from app.clients.minio_store import MinioStore
from app.clients.neo4j import Neo4jWriter
from app.clients.qdrant import QdrantWriter
from app.dedup_store import purge_tenant_dedup_keys
from app.events import publish_tenant_purged


class PurgeConfirmationRequired(Exception):
    """Raised when a destructive purge is attempted without confirm=true."""


def purge_tenant(
    tenant_id: str,
    *,
    dry_run: bool = False,
    confirm: bool = False,
) -> dict[str, object]:
    catalog = get_catalog_store()
    scope = catalog.tenant_scope(tenant_id)
    if dry_run:
        return {
            "dry_run": True,
            "tenant_id": tenant_id,
            "scope": scope,
        }
    if not confirm:
        raise PurgeConfirmationRequired("Set confirm=true to purge tenant data")

    qdrant = QdrantWriter()
    neo4j = Neo4jWriter()
    minio = MinioStore()
    try:
        qdrant_points = qdrant.delete_tenant(
            tenant_id=tenant_id,
            expected_points=scope.get("chunks"),
        )
        neo4j_nodes = neo4j.purge_tenant(tenant_id=tenant_id)
        minio_objects = minio.purge_tenant_prefix(tenant_id)
        catalog_deleted = catalog.purge_tenant(tenant_id)
        dedup_keys = purge_tenant_dedup_keys(tenant_id)
    finally:
        neo4j.close()

    publish_tenant_purged(tenant_id=tenant_id)
    return {
        "tenant_id": tenant_id,
        "purged": True,
        "scope": scope,
        "qdrant_points": qdrant_points,
        "neo4j_nodes": neo4j_nodes,
        "minio_objects": minio_objects,
        "catalog": catalog_deleted,
        "dedup_keys": dedup_keys,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Purge all tenant data (E-21)")
    parser.add_argument("tenant_id", help="Tenant identifier to purge")
    parser.add_argument("--dry-run", action="store_true", help="Report scope only")
    parser.add_argument("--confirm", action="store_true", help="Required for destructive purge")
    args = parser.parse_args(argv)

    try:
        result = purge_tenant(args.tenant_id, dry_run=args.dry_run, confirm=args.confirm)
    except PurgeConfirmationRequired as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
