"""OBS-P3 OTel overhead compare tests."""

from __future__ import annotations

from benchmarks.benchmark_rag import _check_otel_overhead, _otel_overhead_ratio


def test_otel_overhead_ratio() -> None:
    assert _otel_overhead_ratio(baseline_p95=100, otel_p95=104) == 1.04
    assert _otel_overhead_ratio(baseline_p95=0, otel_p95=0) == 0.0


def test_otel_overhead_passes_within_five_percent() -> None:
    _, failures = _check_otel_overhead(baseline_p95=100, otel_p95=104, max_ratio=1.05)
    assert failures == []


def test_otel_overhead_fails_above_threshold() -> None:
    _, failures = _check_otel_overhead(baseline_p95=100, otel_p95=110, max_ratio=1.05)
    assert len(failures) == 1
    assert "otel overhead" in failures[0]
