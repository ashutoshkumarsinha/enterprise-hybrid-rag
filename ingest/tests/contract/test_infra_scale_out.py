"""INF-P6 scale-out read replica documentation contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_scale_out_doc_exists() -> None:
    doc = (REPO_ROOT / "infra/docs/SCALE_OUT.md").read_text(encoding="utf-8")
    assert "INF-P6" in doc
    assert "Qdrant read replica" in doc
    assert "CATALOG_DSN_RO" in doc
