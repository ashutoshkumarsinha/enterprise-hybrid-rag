"""OBS-P5 Prometheus SLO alert rules contract."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMETHEUS_CONFIG = REPO_ROOT / "observability" / "collector" / "prometheus.yml"
ALERT_RULES = REPO_ROOT / "observability" / "alerts" / "prometheus-rules.yaml"
COMPOSE = REPO_ROOT / "observability" / "compose" / "docker-compose.yml"


def test_prometheus_config_loads_alert_rules() -> None:
    text = PROMETHEUS_CONFIG.read_text(encoding="utf-8")
    assert "rule_files:" in text
    assert "/etc/prometheus/alerts/prometheus-rules.yaml" in text


def test_compose_mounts_prometheus_alert_rules() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "prometheus-rules.yaml:/etc/prometheus/alerts/prometheus-rules.yaml" in text


def test_prometheus_rules_define_ttft_p95_alert() -> None:
    text = ALERT_RULES.read_text(encoding="utf-8")
    assert "QueryTTFTp95High" in text
    assert "rag_ttft_ms_bucket" in text
    assert re.search(r"for:\s+30m", text)
    assert "> 2000" in text


def test_prometheus_rules_define_retrieve_and_ingest_slos() -> None:
    text = ALERT_RULES.read_text(encoding="utf-8")
    assert "QueryRetrieveStageP95High" in text
    assert 'stage="retrieve"' in text
    assert "IngestThroughputLow" in text
    assert "TraceExportFailure" in text
