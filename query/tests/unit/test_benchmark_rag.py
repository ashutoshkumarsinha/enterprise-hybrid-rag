"""Smoke test benchmark_rag CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def test_benchmark_rag_limit_1() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(BENCHMARKS / "benchmark_rag.py"),
            "--limit",
            "1",
            "--golden-set",
            str(BENCHMARKS / "golden_set.json.example"),
            "--output",
            str(BENCHMARKS / "last_run_test.json"),
        ],
        cwd=BENCHMARKS.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads((BENCHMARKS / "last_run_test.json").read_text(encoding="utf-8"))
    assert out["count"] == 1
    assert "stages_ms" in out
    assert "total" in out["stages_ms"]
