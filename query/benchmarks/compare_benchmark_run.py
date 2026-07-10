#!/usr/bin/env python3
"""Compare benchmark run JSON against baselines — platform §13."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare last_run.json to baselines.json")
    parser.add_argument("run", type=Path, nargs="?", default=Path("benchmarks/last_run.json"))
    parser.add_argument("baseline", type=Path, nargs="?", default=Path("benchmarks/baselines.json"))
    parser.add_argument("--fail-ratio", type=float, default=1.1)
    args = parser.parse_args(argv)

    if not args.run.exists():
        print(f"run file missing: {args.run}", file=sys.stderr)
        return 1
    if not args.baseline.exists():
        print(f"baseline missing: {args.baseline}", file=sys.stderr)
        return 1

    run = json.loads(args.run.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    run_total = run.get("stages_ms", {}).get("total", {}).get("p95", 0)
    base_total = baseline.get("rag", {}).get("total_p95_ms", 0)
    ratio_max = baseline.get("regression_thresholds", {}).get(
        "rag_total_p95_ratio_max", args.fail_ratio
    )
    failures: list[str] = []
    if base_total and run_total > base_total * ratio_max:
        failures.append(f"total p95 {run_total} > baseline {base_total} × {ratio_max}")

    run_scope = run.get("scope_accuracy")
    base_scope = baseline.get("rag", {}).get("scope_accuracy")
    min_delta = baseline.get("regression_thresholds", {}).get("scope_accuracy_min_delta", -0.02)
    if base_scope is not None and run_scope is not None:
        if run_scope < base_scope + min_delta:
            failures.append(f"scope_accuracy {run_scope} < baseline {base_scope} + {min_delta}")

    if failures:
        for msg in failures:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 2
    print("OK: within baseline thresholds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
