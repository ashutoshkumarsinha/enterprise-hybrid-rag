#!/usr/bin/env python3
"""E-25 embed dimension consistency check and migration checklist.

Usage:
  python scripts/migrate_embed_dimension.py --dry-run
  python scripts/migrate_embed_dimension.py --check-qdrant --target-dim 768
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ENV_DIM_RE = re.compile(r"^EMBED_DIMENSION\s*=\s*(\d+)\s*$", re.MULTILINE)
TOML_DIM_RE = re.compile(r"^embed_dimension\s*=\s*(\d+)\s*$", re.MULTILINE)

CHECK_PATHS = [
    REPO_ROOT / "infra" / "config" / "infra.toml.example",
    REPO_ROOT / "ingest" / ".env.example",
    REPO_ROOT / "query" / ".env.example",
    REPO_ROOT / "inference" / ".env.example",
    REPO_ROOT / "modules" / "SHARED_CONTRACTS.md",
]


def _read_dim_from_file(path: Path) -> int | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        m = re.search(r"embed_dimension\s*=\s*(\d+)", text)
        return int(m.group(1)) if m else None
    m = TOML_DIM_RE.search(text) or ENV_DIM_RE.search(text)
    return int(m.group(1)) if m else None


def collect_dimensions() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in CHECK_PATHS:
        dim = _read_dim_from_file(path)
        if dim is not None:
            found[str(path.relative_to(REPO_ROOT))] = dim
    return found


def qdrant_collection_dim(url: str, collection: str) -> int | None:
    req = urllib.request.Request(f"{url.rstrip('/')}/collections/{collection}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    try:
        return int(body["result"]["config"]["params"]["vectors"]["default"]["size"])
    except (KeyError, TypeError, ValueError):
        return None


def print_checklist(target: int) -> None:
    print("\nE-25 migration checklist (see docs/EMBED_DIMENSION_MIGRATION.md):")
    steps = [
        f"Set embed_dimension={target} in infra.toml + all EMBED_DIMENSION env files",
        "Deploy inference embed model with matching output dimension",
        f"Create new Qdrant collection: QDRANT_COLLECTION=..._v2 EMBED_DIMENSION={target} make -C infra init-db",
        "Backfill/re-ingest all tenants into new collection",
        "Flip QDRANT_COLLECTION + rolling restart query",
        "Delete old collection after validation window",
    ]
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")


def main() -> int:
    parser = argparse.ArgumentParser(description="E-25 embed dimension migration helper")
    parser.add_argument("--dry-run", action="store_true", help="Check config consistency (default)")
    parser.add_argument("--target-dim", type=int, default=None, help="Expected dimension")
    parser.add_argument("--check-qdrant", action="store_true", help="Compare Qdrant collection dim")
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--collection", default="enterprise_hybrid_rag")
    args = parser.parse_args()

    dims = collect_dimensions()
    if not dims:
        print("ERROR: no embed_dimension values found in checked paths", file=sys.stderr)
        return 1

    values = set(dims.values())
    target = args.target_dim if args.target_dim is not None else (values.pop() if len(values) == 1 else None)

    print("Configured embed_dimension values:")
    for rel, dim in sorted(dims.items()):
        mark = "OK" if target is None or dim == target else "MISMATCH"
        print(f"  {rel}: {dim} [{mark}]")

    mismatches = [rel for rel, dim in dims.items() if target is not None and dim != target]
    if len(set(dims.values())) > 1 or mismatches:
        print("\nFAIL: inconsistent embed_dimension across modules", file=sys.stderr)
        if target is not None:
            print_checklist(target)
        return 1

    if args.check_qdrant:
        live = qdrant_collection_dim(args.qdrant_url, args.collection)
        if live is None:
            print(f"\nWARN: could not read Qdrant collection {args.collection!r} at {args.qdrant_url}")
        elif target is not None and live != target:
            print(f"\nFAIL: Qdrant collection dim={live} != target={target}", file=sys.stderr)
            print_checklist(target)
            return 1
        elif live is not None:
            print(f"\nQdrant {args.collection}: dim={live} OK")

    if target is not None:
        print(f"\nPASS: all sources agree on embed_dimension={target}")
    else:
        print("\nPASS: all sources agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
