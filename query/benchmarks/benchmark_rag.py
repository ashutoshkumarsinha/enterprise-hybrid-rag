#!/usr/bin/env python3
"""Golden-set RAG benchmark — latency stages + optional Ragas (LG-4).

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §13.2.1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BENCHMARKS_DIR = Path(__file__).resolve().parent
REPO_QUERY_DIR = BENCHMARKS_DIR.parent
sys.path.insert(0, str(REPO_QUERY_DIR))

from app.client_factory import get_qdrant_client, reset_clients  # noqa: E402
from app.rag_graph import run_rag_pipeline  # noqa: E402
from app.rag_state import RAGState  # noqa: E402


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return int(ordered[rank])


def _stage_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    stages: dict[str, list[int]] = {}
    for row in rows:
        for stage, ms in (row.get("timings_ms") or {}).items():
            stages.setdefault(stage, []).append(int(ms))
        total = sum(int(v) for v in (row.get("timings_ms") or {}).values())
        stages.setdefault("total", []).append(total)
    return {
        stage: {"p50": _percentile(vals, 50), "p95": _percentile(vals, 95)}
        for stage, vals in stages.items()
    }


def _load_golden_set(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("golden set must be a JSON array")
    return data


async def _run_row(row: dict[str, Any]) -> dict[str, Any]:
    explicit = bool(row.get("document_id") or row.get("collection_id"))
    state = RAGState(
        query=row["question"],
        tenant_id=row.get("tenant_id", "dev"),
        collection_id=row.get("collection_id", ""),
        document_id=row.get("document_id"),
        version_id=row.get("version_id"),
        explicit_scope=explicit,
        skip_supervisor=explicit,
        graph_enrich_enabled=True,
        timings_ms={},
        from_cache=False,
        abstained=False,
    )
    final = await run_rag_pipeline(state)
    top_doc = None
    chunks = final.get("retrieved_chunks") or []
    if chunks:
        top_doc = chunks[0].get("document_id")
    expect = row.get("expect_document_id")
    scope_ok = expect is None or top_doc == expect
    return {
        "id": row.get("id"),
        "timings_ms": final.get("timings_ms") or {},
        "abstained": final.get("abstained", False),
        "scope_ok": scope_ok,
        "answer_text": final.get("answer_text", ""),
        "retrieved_chunks": chunks,
        "ground_truth": row.get("ground_truth"),
        "question": row.get("question"),
    }


async def _run_benchmark(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(await _run_row(row))
    return results


def _maybe_ragas(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_recall, faithfulness
    except ImportError:
        print("WARN: ragas not installed — skip --ragas", file=sys.stderr)
        return None

    records = []
    for row in rows:
        contexts = [c.get("text", "") for c in row.get("retrieved_chunks") or [] if c.get("text")]
        records.append(
            {
                "question": row.get("question", ""),
                "answer": row.get("answer_text", ""),
                "contexts": contexts or [""],
                "ground_truth": row.get("ground_truth", ""),
            }
        )
    dataset = Dataset.from_list(records)
    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_recall])
    scores = {k: float(v) for k, v in result.items() if isinstance(v, (int, float))}
    return {"scores": scores, "count": len(records)}


def _check_thresholds(
    *,
    stages: dict[str, dict[str, int]],
    ragas: dict[str, Any] | None,
    args: argparse.Namespace,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    total_p95 = stages.get("total", {}).get("p95", 0)
    if args.warn_total_p95_ms and total_p95 > args.warn_total_p95_ms:
        warnings.append(f"total p95 {total_p95}ms > warn {args.warn_total_p95_ms}ms")
    if args.fail_total_p95_ms and total_p95 > args.fail_total_p95_ms:
        failures.append(f"total p95 {total_p95}ms > fail {args.fail_total_p95_ms}ms")
    if ragas and "scores" in ragas:
        scores = ragas["scores"]
        fail_checks = [
            ("faithfulness", args.fail_faithfulness),
            ("answer_relevancy", args.fail_answer_relevancy),
            ("context_recall", args.fail_context_recall),
        ]
        warn_checks = [
            ("faithfulness", args.warn_faithfulness),
            ("answer_relevancy", args.warn_answer_relevancy),
            ("context_recall", args.warn_context_recall),
        ]
        for key, threshold in fail_checks:
            if threshold is None:
                continue
            value = scores.get(key)
            if value is None:
                continue
            if value < threshold:
                failures.append(f"{key} {value:.3f} < {threshold}")
        for key, threshold in warn_checks:
            if threshold is None:
                continue
            value = scores.get(key)
            if value is None:
                continue
            if value < threshold:
                warnings.append(f"{key} {value:.3f} < warn {threshold}")
    return warnings, failures


def _require_live_stack() -> None:
    qdrant = get_qdrant_client()
    if qdrant.is_stub:
        raise SystemExit("live-stack requested but Qdrant is in stub mode (set QDRANT_URL)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG golden-set benchmark")
    parser.add_argument("--golden-set", type=Path, default=BENCHMARKS_DIR / "golden_set.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ragas", action="store_true")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--output", type=Path, default=BENCHMARKS_DIR / "last_run.json")
    parser.add_argument("--ragas-output", type=Path, default=BENCHMARKS_DIR / "last_ragas.json")
    parser.add_argument("--fail-faithfulness", type=float, default=None)
    parser.add_argument("--fail-answer-relevancy", type=float, default=None)
    parser.add_argument("--fail-context-recall", type=float, default=None)
    parser.add_argument("--warn-faithfulness", type=float, default=None)
    parser.add_argument("--warn-answer-relevancy", type=float, default=None)
    parser.add_argument("--warn-context-recall", type=float, default=None)
    parser.add_argument("--fail-total-p95-ms", type=int, default=None)
    parser.add_argument("--warn-total-p95-ms", type=int, default=None)
    parser.add_argument("--compare-otel", action="store_true", help="OBS-P3 placeholder")
    parser.add_argument("--live-stack", action="store_true")
    args = parser.parse_args(argv)

    if args.live_stack or os.environ.get("LIVE_STACK", "").lower() in ("1", "true", "yes"):
        _require_live_stack()

    golden_path = args.golden_set
    if not golden_path.exists():
        golden_path = BENCHMARKS_DIR / "golden_set.json.example"
    rows = _load_golden_set(golden_path)
    if args.limit is not None:
        rows = rows[: args.limit]

    reset_clients()
    results = asyncio.run(_run_benchmark(rows))
    stages = _stage_stats(results)
    scope_hits = sum(1 for r in results if r.get("scope_ok"))
    scope_accuracy = scope_hits / len(results) if results else 0.0
    abstain_rate = sum(1 for r in results if r.get("abstained")) / len(results) if results else 0.0

    summary = {
        "run_at": datetime.now(UTC).isoformat(),
        "count": len(results),
        "stages_ms": stages,
        "scope_accuracy": round(scope_accuracy, 4),
        "abstain_rate": round(abstain_rate, 4),
        "golden_set": str(golden_path),
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

    if args.write_baseline:
        baseline_path = BENCHMARKS_DIR / "baselines.json"
        baseline = {
            "profile": os.environ.get("INFERENCE_PROFILE", "gpu_24gb"),
            "index_schema_version": 1,
            "updated": datetime.now(UTC).date().isoformat(),
            "rag": {
                "total_p95_ms": stages.get("total", {}).get("p95", 0),
                "stages_p95_ms": {k: v.get("p95", 0) for k, v in stages.items()},
                "scope_accuracy": scope_accuracy,
            },
        }
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baseline {baseline_path}")

    ragas_out = _maybe_ragas(results) if args.ragas else None
    if ragas_out:
        args.ragas_output.write_text(json.dumps(ragas_out, indent=2) + "\n", encoding="utf-8")

    if args.compare_otel:
        print("WARN: --compare-otel not implemented (OBS-P3)", file=sys.stderr)

    warnings, failures = _check_thresholds(stages=stages, ragas=ragas_out, args=args)
    for msg in warnings:
        print(f"WARN: {msg}", file=sys.stderr)
    for msg in failures:
        print(f"FAIL: {msg}", file=sys.stderr)
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
