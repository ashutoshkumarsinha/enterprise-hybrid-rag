#!/usr/bin/env python3
"""Validate release matrix config alignment (E-03)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPAT = ROOT / "docs" / "releases" / "compatibility.json"
IMAGES = ROOT / "docs" / "releases" / "images.json"


def _read_index_schema_version(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'index_schema_version\s*=\s*["\']?(\d+)["\']?', text)
    if not match:
        raise ValueError(f"index_schema_version not found in {path}")
    return int(match.group(1))


def validate() -> list[str]:
    issues: list[str] = []
    compat = json.loads(COMPAT.read_text(encoding="utf-8"))
    images = json.loads(IMAGES.read_text(encoding="utf-8"))

    target_rows = [row for row in compat["releases"] if row.get("status") == "target"]
    if len(target_rows) != 1:
        issues.append("expected exactly one release row with status=target")
        return issues

    target = target_rows[0]
    expected_schema = int(target["index_schema_version"])
    for plane, rel_path in compat.get("config_index_schema_version", {}).items():
        path = ROOT / rel_path
        if not path.is_file():
            issues.append(f"missing config for {plane}: {rel_path}")
            continue
        actual = _read_index_schema_version(path)
        if actual != expected_schema:
            issues.append(
                f"{plane} index_schema_version={actual} != target platform {expected_schema}"
            )

    catalog_names = {item["name"] for item in images["images"]}
    for item in images["images"]:
        packer_path = ROOT / item["packer"]
        if not packer_path.is_file():
            issues.append(f"images.json references missing packer file: {item['packer']}")
            continue
        packer_text = packer_path.read_text(encoding="utf-8")
        if item["name"] not in packer_text:
            issues.append(f"{item['name']} not found in {item['packer']}")

    if len(catalog_names) < 10:
        issues.append("images.json catalog unexpectedly small")

    return issues


def main() -> int:
    issues = validate()
    if issues:
        print("release matrix validation FAILED:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    print("release matrix validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
