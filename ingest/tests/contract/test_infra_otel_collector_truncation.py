"""OBS-P2 query attribute truncation across all OTel collector profiles."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COLLECTOR_DIR = REPO_ROOT / "observability" / "collector"

TRUNCATION_MARKERS = (
    "attributes/redact:",
    "key: rag.query",
    "key: query",
    "truncated_length: 120",
)

COLLECTOR_CONFIGS = (
    "otel-collector-config.yaml",
    "otel-collector-config.prod.yaml",
    "otel-collector-config.signoz.yaml",
)


def test_all_collector_profiles_define_truncation() -> None:
    for name in COLLECTOR_CONFIGS:
        path = COLLECTOR_DIR / name
        assert path.is_file(), f"missing collector config: {path}"
        text = path.read_text(encoding="utf-8")
        for marker in TRUNCATION_MARKERS:
            assert marker in text, f"{name} missing OBS-P2 marker: {marker}"


def test_all_collector_trace_pipelines_apply_truncation() -> None:
    for name in COLLECTOR_CONFIGS:
        text = (COLLECTOR_DIR / name).read_text(encoding="utf-8")
        pipelines = text.split("  pipelines:", 1)[1]
        traces_block = pipelines.split("\n    traces:", 1)[1].split("\n    metrics:", 1)[0]
        assert "attributes/redact" in traces_block, f"{name} trace pipeline missing attributes/redact"


def test_metrics_pipelines_do_not_sample_or_truncate_queries() -> None:
    for name in ("otel-collector-config.prod.yaml", "otel-collector-config.yaml"):
        text = (COLLECTOR_DIR / name).read_text(encoding="utf-8")
        pipelines = text.split("  pipelines:", 1)[1]
        metrics_block = pipelines.split("\n    metrics:", 1)[1].split("\n    logs:", 1)[0]
        assert "attributes/redact" not in metrics_block
        assert "probabilistic_sampler" not in metrics_block
