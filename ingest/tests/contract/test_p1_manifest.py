"""P1 implementation-ready depth gate — E-14 through E-19."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "docs" / "releases" / "p1_manifest.json"


def test_p1_manifest_exists() -> None:
    assert MANIFEST.is_file()


def test_p1_deliverables_on_disk() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(data["items"]) == 6
    ids = {item["id"] for item in data["items"]}
    assert ids == {"E-14", "E-15", "E-16", "E-17", "E-18", "E-19"}
    for item in data["items"]:
        for rel in item["paths"]:
            path = REPO_ROOT / rel
            if rel.endswith("/"):
                assert path.is_dir(), f"{item['id']} missing directory {rel}"
            else:
                assert path.exists(), f"{item['id']} missing path {rel}"


def test_p1_contract_tests_exist() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing: list[str] = []
    for item in data["items"]:
        for rel in item.get("contract_tests", []):
            if not (REPO_ROOT / rel).is_file():
                missing.append(f"{item['id']}: {rel}")
    assert not missing, f"missing P1 contract tests: {missing}"
