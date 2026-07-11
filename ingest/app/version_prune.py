"""Nightly document version retention prune — E-22 / OD2."""

from __future__ import annotations

import argparse
import json
import os
import sys

from app.catalog_store import get_catalog_store
from app.clients.neo4j import Neo4jWriter
from app.clients.qdrant import QdrantWriter


def _default_keep_count() -> int:
    return int(os.environ.get("VERSION_RETENTION_COUNT", "3"))


def prune_versions(*, keep_count: int | None = None, dry_run: bool = False) -> dict[str, int | list[dict]]:
    keep = keep_count if keep_count is not None else _default_keep_count()
    catalog = get_catalog_store()
    candidates = catalog.list_prunable_versions(keep_count=keep)
    if dry_run:
        return {
            "dry_run": True,
            "keep_count": keep,
            "candidates": len(candidates),
            "versions": candidates,
        }

    qdrant = QdrantWriter()
    neo4j = Neo4jWriter()
    qdrant_points = 0
    neo4j_nodes = 0
    try:
        for version in candidates:
            qdrant_points += qdrant.delete_version(
                tenant_id=version["tenant_id"],
                collection_id=version["collection_id"],
                document_id=version["document_id"],
                version_id=version["version_id"],
                expected_points=version.get("chunk_count"),
            )
            neo4j_nodes += neo4j.prune_version(
                tenant_id=version["tenant_id"],
                document_id=version["document_id"],
                version_id=version["version_id"],
            )
    finally:
        neo4j.close()

    catalog_rows = catalog.delete_versions(candidates)
    return {
        "pruned": len(candidates),
        "keep_count": keep,
        "qdrant_points": qdrant_points,
        "neo4j_nodes": neo4j_nodes,
        "catalog_rows": catalog_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prune old document versions (E-22)")
    parser.add_argument(
        "--keep-count",
        type=int,
        default=None,
        help="Override VERSION_RETENTION_COUNT (default from env)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List candidates only; no deletes")
    args = parser.parse_args(argv)

    result = prune_versions(keep_count=args.keep_count, dry_run=args.dry_run)
    print(json.dumps(result))
    if args.dry_run:
        return 0
    if result.get("pruned", 0) == 0:
        print("INFO: no versions pruned", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
