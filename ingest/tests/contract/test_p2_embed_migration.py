"""E-25 embedding dimension migration playbook contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "docs" / "EMBED_DIMENSION_MIGRATION.md"
SCRIPT = REPO_ROOT / "scripts" / "migrate_embed_dimension.py"
SPEC = REPO_ROOT / "ENTERPRISE_HYBRID_RAG_SPEC.md"


def test_embed_migration_doc_resolves_oq2() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "E-25" in text
    assert "OQ2" in text
    assert "reindex" in text.lower() or "re-embed" in text.lower()
    assert "migrate_embed_dimension.py" in text


def test_migrate_embed_dimension_script_exists_and_passes_dry_run() -> None:
    assert SCRIPT.is_file()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "embed_dimension" in result.stdout.lower()


def test_spec_mentions_e25_playbook() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "E-25" in spec
