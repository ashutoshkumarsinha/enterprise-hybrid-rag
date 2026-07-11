"""Smoke test benchmark_ingest CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def test_benchmark_ingest_mock() -> None:
    out = BENCHMARKS / "last_ingest_run_test.json"
    result = subprocess.run(
        [
            sys.executable,
            str(BENCHMARKS / "benchmark_ingest.py"),
            "--mock",
            "--chunks",
            "64",
            "--batch-size",
            "16",
            "--output",
            str(out),
            "--warn-chunks-per-min",
            "100",
        ],
        cwd=BENCHMARKS.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["mode"] == "mock"
    assert summary["validated"] == 64
    assert summary["chunks_per_min"] >= 100
