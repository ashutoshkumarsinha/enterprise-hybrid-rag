"""Tests for compare_benchmark_run.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_compare_within_baseline(tmp_path: Path) -> None:
    run = tmp_path / "run.json"
    baseline = tmp_path / "baseline.json"
    _write(
        run,
        {"stages_ms": {"total": {"p95": 8000}}, "scope_accuracy": 0.95},
    )
    _write(
        baseline,
        {
            "rag": {"total_p95_ms": 8500, "scope_accuracy": 0.92},
            "regression_thresholds": {"rag_total_p95_ratio_max": 1.1, "scope_accuracy_min_delta": -0.02},
        },
    )
    result = subprocess.run(
        [sys.executable, str(BENCHMARKS / "compare_benchmark_run.py"), str(run), str(baseline)],
        cwd=BENCHMARKS.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_compare_fails_on_latency_regression(tmp_path: Path) -> None:
    run = tmp_path / "run.json"
    baseline = tmp_path / "baseline.json"
    _write(run, {"stages_ms": {"total": {"p95": 12000}}, "scope_accuracy": 0.95})
    _write(
        baseline,
        {
            "rag": {"total_p95_ms": 8500, "scope_accuracy": 0.92},
            "regression_thresholds": {"rag_total_p95_ratio_max": 1.1},
        },
    )
    result = subprocess.run(
        [sys.executable, str(BENCHMARKS / "compare_benchmark_run.py"), str(run), str(baseline)],
        cwd=BENCHMARKS.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "total p95" in result.stderr
