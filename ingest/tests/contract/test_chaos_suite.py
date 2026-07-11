"""E-26 chaos suite contract — spec §13.1 monthly staging scenarios."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHAOS_DIR = REPO_ROOT / "scripts" / "chaos"


def test_chaos_assets_exist() -> None:
    assert (CHAOS_DIR / "chaos_suite.py").is_file()
    assert (CHAOS_DIR / "scenarios.json").is_file()
    assert (REPO_ROOT / "scripts" / "run-chaos.sh").is_file()


def test_scenarios_cover_spec_table() -> None:
    data = json.loads((CHAOS_DIR / "scenarios.json").read_text(encoding="utf-8"))
    ids = {item["id"] for item in data["scenarios"]}
    assert ids == {
        "redis_unavailable",
        "embed_timeout",
        "qdrant_slow",
        "vllm_restart",
        "ingest_flood",
    }


def test_chaos_suite_dry_run() -> None:
    py = REPO_ROOT / "query" / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    result = subprocess.run(
        [str(py), str(CHAOS_DIR / "chaos_suite.py"), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["scenario_count"] == 5
