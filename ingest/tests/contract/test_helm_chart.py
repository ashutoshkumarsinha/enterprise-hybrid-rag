"""E-19 Helm chart sketch contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHART = REPO_ROOT / "deploy" / "helm" / "hybrid-rag"
VALUES = CHART / "values.yaml"
VALUES_PROD = CHART / "values-prod.yaml"


def test_helm_chart_metadata_exists() -> None:
    chart_yaml = (CHART / "Chart.yaml").read_text(encoding="utf-8")
    assert "name: hybrid-rag" in chart_yaml
    assert (CHART / "templates" / "query.yaml").is_file()
    assert (CHART / "templates" / "ingest.yaml").is_file()


def test_values_define_store_modes_and_hpa() -> None:
    text = VALUES.read_text(encoding="utf-8")
    assert "stores:" in text
    assert "mode: selfHosted" in text
    assert "autoscaling:" in text
    assert "cronJobs:" in text


def test_prod_values_use_managed_stores() -> None:
    text = VALUES_PROD.read_text(encoding="utf-8")
    assert "mode: managed" in text
    assert "minReplicas: 3" in text


def test_templates_include_ingress_and_cronjobs() -> None:
    ingress = (CHART / "templates" / "ingress.yaml").read_text(encoding="utf-8")
    cron = (CHART / "templates" / "cronjobs.yaml").read_text(encoding="utf-8")
    assert "proxy-buffering" in ingress
    assert "version-prune" in cron
    assert "session-prune" in cron
