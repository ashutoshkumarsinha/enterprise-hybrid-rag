"""E-03/E-04 release matrix and Packer image catalog contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_release_matrix_docs_exist() -> None:
    assert (REPO_ROOT / "docs" / "RELEASE_MATRIX.md").is_file()
    assert (REPO_ROOT / "docs" / "releases" / "compatibility.json").is_file()
    assert (REPO_ROOT / "docs" / "releases" / "images.json").is_file()


def test_compatibility_json_has_target_release() -> None:
    data = json.loads((REPO_ROOT / "docs" / "releases" / "compatibility.json").read_text())
    targets = [row for row in data["releases"] if row.get("status") == "target"]
    assert len(targets) == 1
    assert targets[0]["platform"] == "rag-v1.0.0"
    assert targets[0]["index_schema_version"] == 1
    assert set(targets[0]["sub_projects"]) == {
        "infra",
        "inference",
        "observability",
        "ingest",
        "query",
    }


def test_images_json_catalog_matches_packer() -> None:
    data = json.loads((REPO_ROOT / "docs" / "releases" / "images.json").read_text())
    names = {item["name"] for item in data["images"]}
    assert "hybrid-rag-query" in names
    assert "hybrid-rag-ingest-orchestrator" in names
    assert "hybrid-rag-qdrant" in names
    assert len(names) >= 16


def test_packer_glossary_documents_vllm_upstream() -> None:
    text = (REPO_ROOT / "packer" / "versions.pkrvars.hcl.example").read_text(encoding="utf-8")
    assert "vllm_upstream" in text
    assert "image_tag" in text
    assert "Field glossary" in text


def test_validate_release_matrix_script() -> None:
    py = REPO_ROOT / "query" / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    result = subprocess.run(
        [str(py), str(REPO_ROOT / "scripts" / "validate_release_matrix.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
