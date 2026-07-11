"""P2 enterprise hardening gate — E-34, E-24, E-25 + manifest."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "docs" / "releases" / "p2_manifest.json"


def test_p2_manifest_exists() -> None:
    assert MANIFEST.is_file()


def test_p2_deliverables_on_disk() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(data["items"]) == 11
    ids = {item["id"] for item in data["items"]}
    expected = {
        "E-34", "E-21", "E-22", "E-23", "E-44",
        "E-24", "E-25", "E-26", "E-27", "E-28", "E-29",
    }
    assert ids == expected
    for item in data["items"]:
        for rel in item["paths"]:
            path = REPO_ROOT / rel
            assert path.exists(), f"{item['id']} missing path {rel}"


def test_p2_contract_tests_exist() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing: list[str] = []
    for item in data["items"]:
        for rel in item.get("contract_tests", []):
            if not (REPO_ROOT / rel).is_file():
                missing.append(f"{item['id']}: {rel}")
    assert not missing, f"missing P2 contract tests: {missing}"
