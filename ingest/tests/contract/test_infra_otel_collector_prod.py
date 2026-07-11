"""OBS-P1/OBS-P2 production OTel collector config contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROD_CONFIG = REPO_ROOT / "observability" / "collector" / "otel-collector-config.prod.yaml"


def test_prod_collector_config_exists() -> None:
    assert PROD_CONFIG.is_file(), f"missing prod collector config: {PROD_CONFIG}"


def test_prod_collector_has_probabilistic_sampler() -> None:
    text = PROD_CONFIG.read_text(encoding="utf-8")
    assert "probabilistic_sampler:" in text
    assert "sampling_percentage: ${env:TRACE_SAMPLING_PERCENTAGE}" in text
    assert "processors: [memory_limiter, resource, attributes/redact, probabilistic_sampler, batch]" in text


def test_prod_collector_truncates_query_attributes() -> None:
    text = PROD_CONFIG.read_text(encoding="utf-8")
    assert "attributes/redact:" in text
    assert "key: rag.query" in text
    assert "key: query" in text


def test_prod_collector_metrics_pipeline_unsampled() -> None:
    text = PROD_CONFIG.read_text(encoding="utf-8")
    pipelines = text.split("  pipelines:", 1)[1]
    metrics_block = pipelines.split("\n    metrics:", 1)[1].split("\n    logs:", 1)[0]
    assert "processors: [memory_limiter, resource, batch]" in metrics_block
    assert "probabilistic_sampler" not in metrics_block
