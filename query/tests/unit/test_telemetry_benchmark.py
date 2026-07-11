"""Telemetry reset/benchmark mode tests."""

from __future__ import annotations

from app.telemetry import get_tracer, is_otel_configured, reset_otel, setup_otel_benchmark


def test_setup_otel_benchmark_enables_tracer() -> None:
    reset_otel()
    assert is_otel_configured() is False
    setup_otel_benchmark()
    assert is_otel_configured() is True
    tracer = get_tracer("test")
    with tracer.start_as_current_span("unit.span"):
        pass
    reset_otel()
    assert is_otel_configured() is False
