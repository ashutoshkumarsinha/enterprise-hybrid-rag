#!/usr/bin/env python3
"""Cross-plane config alignment checks for rag-v1.0 gate."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EMBED_PATHS = [
    ROOT / "infra/config/infra.toml.example",
    ROOT / "ingest/.env.example",
    ROOT / "query/.env.example",
    ROOT / "modules/SHARED_CONTRACTS.md",
]

SCHEMA_PATHS = [
    ROOT / "infra/config/infra.toml.example",
    ROOT / "ingest/config/ingest.toml.example",
    ROOT / "query/config/query.toml.example",
]

ENV_DIM = re.compile(r"^EMBED_DIMENSION\s*=\s*(\d+)\s*$", re.MULTILINE)
TOML_DIM = re.compile(r"^embed_dimension\s*=\s*(\d+)\s*$", re.MULTILINE)
TOML_SCHEMA = re.compile(r'^index_schema_version\s*=\s*["\']?(\d+)["\']?', re.MULTILINE)
MD_DIM = re.compile(r"embed_dimension\s*=\s*(\d+)")
MD_SCHEMA = re.compile(r"index_schema_version\s*=\s*(\d+)")


def _read_dim(path: Path) -> int | None:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        m = MD_DIM.search(text)
        return int(m.group(1)) if m else None
    m = TOML_DIM.search(text) or ENV_DIM.search(text)
    return int(m.group(1)) if m else None


def _read_schema(path: Path) -> int | None:
    text = path.read_text(encoding="utf-8")
    m = TOML_SCHEMA.search(text) or MD_SCHEMA.search(text)
    return int(m.group(1)) if m else None


def validate() -> list[str]:
    issues: list[str] = []

    dims = {_read_dim(p) for p in EMBED_PATHS}
    dims.discard(None)
    if len(dims) != 1:
        issues.append(f"embed_dimension mismatch across planes: {dims}")

    schemas = {_read_schema(p) for p in SCHEMA_PATHS}
    schemas.discard(None)
    if len(schemas) != 1:
        issues.append(f"index_schema_version mismatch: {schemas}")

    migration = ROOT / "ingest/migrations/005_tenant_qdrant_suffix_v1.sql"
    if not migration.is_file():
        issues.append("missing migration 005_tenant_qdrant_suffix_v1.sql")

    return issues


def main() -> int:
    issues = validate()
    if issues:
        print("config alignment FAILED:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    print("config alignment OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
