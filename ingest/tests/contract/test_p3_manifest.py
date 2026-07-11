"""P3 advanced product gate — E-30, E-32, E-33."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "docs" / "releases" / "p3_manifest.json"


def test_p3_manifest_exists() -> None:
    assert MANIFEST.is_file()


def test_p3_deliverables_on_disk() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(data["items"]) == 3
    ids = {item["id"] for item in data["items"]}
    assert ids == {"E-30", "E-32", "E-33"}
    for item in data["items"]:
        for rel in item["paths"]:
            path = REPO_ROOT / rel
            assert path.exists(), f"{item['id']} missing path {rel}"


def test_p3_contract_tests_exist() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing: list[str] = []
    for item in data["items"]:
        for rel in item.get("contract_tests", []):
            if not (REPO_ROOT / rel).is_file():
                missing.append(f"{item['id']}: {rel}")
    assert not missing, f"missing P3 contract tests: {missing}"
