"""FR-40 OTLP histogram metrics (rag_ttft_ms, rag_stage_ms)."""

from __future__ import annotations

import pytest

from app.otel_metrics import (
    is_otel_metrics_configured,
    metrics_enabled,
    record_rag_stage_ms,
    record_rag_ttft_ms,
    reset_otel_metrics,
    setup_otel_metrics,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_otel_metrics()


def test_metrics_enabled_with_otlp_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "otlp")
    assert metrics_enabled() is True


def test_metrics_enabled_with_signoz_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_METRICS_EXPORTER", raising=False)
    monkeypatch.setenv("SIGNOZ_ENABLED", "true")
    assert metrics_enabled() is True


def test_setup_in_memory_histograms() -> None:
    setup_otel_metrics(in_memory=True)
    assert is_otel_metrics_configured() is True


def test_record_rag_stage_ms() -> None:
    recorded: list[tuple[int, dict[str, str] | None]] = []

    class FakeHistogram:
        def record(self, value: int, *, attributes: dict[str, str] | None = None) -> None:
            recorded.append((value, attributes))

    import app.otel_metrics as om

    om._stage_histogram = FakeHistogram()
    record_rag_stage_ms("embed", 45, tenant_id="acme")
    assert recorded[0][0] == 45
    assert recorded[0][1] == {"module_id": "hybrid-rag-query", "stage": "embed"}


def test_record_rag_ttft_ms() -> None:
    recorded: list[int] = []

    class FakeHistogram:
        def record(self, value: int, *, attributes: dict[str, str] | None = None) -> None:
            recorded.append(value)

    import app.otel_metrics as om

    om._ttft_histogram = FakeHistogram()
    record_rag_ttft_ms(120, tenant_id="acme")
    assert recorded == [120]
