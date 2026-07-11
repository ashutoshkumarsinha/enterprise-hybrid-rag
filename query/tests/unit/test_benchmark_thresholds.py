"""Threshold checks for benchmark_rag."""

from __future__ import annotations

import argparse

from benchmarks.benchmark_rag import _check_thresholds


def test_ragas_warn_threshold() -> None:
    args = argparse.Namespace(
        warn_total_p95_ms=None,
        fail_total_p95_ms=None,
        warn_faithfulness=0.80,
        fail_faithfulness=None,
        warn_answer_relevancy=None,
        fail_answer_relevancy=None,
        warn_context_recall=None,
        fail_context_recall=None,
    )
    warnings, failures = _check_thresholds(
        stages={"total": {"p50": 1, "p95": 100}},
        ragas={"scores": {"faithfulness": 0.75}},
        args=args,
    )
    assert not failures
    assert any("faithfulness" in w for w in warnings)
