"""E-23 SigNoz dashboard import automation contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
IMPORT_SCRIPT = REPO_ROOT / "observability" / "scripts" / "import_signoz.py"
DASHBOARD_DIR = REPO_ROOT / "observability" / "dashboards"


def _run_import(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(IMPORT_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT / "observability",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_import_signoz_dry_run_dashboards() -> None:
    payload = _run_import("dashboards")
    dashboards = payload["dashboards"]
    assert len(dashboards) == 2
    titles = {entry["title"] for entry in dashboards}
    assert "Hybrid RAG — Query Latency" in titles
    assert "Hybrid RAG — Ingest Throughput" in titles
    for entry in dashboards:
        assert entry["status"] == "dry-run"
        assert entry["widgets"] >= 3
        body = entry["payload"]
        assert body["version"] == "v5"
        assert body["widgets"][0]["query"]["queryType"] == "promql"


def test_dashboard_stubs_reference_fr40_metrics() -> None:
    query_latency = json.loads(
        (DASHBOARD_DIR / "signoz-query-latency.json").read_text(encoding="utf-8")
    )
    queries = " ".join(panel["query"] for panel in query_latency["panels"])
    assert "rag_ttft_ms" in queries
    assert "rag_stage_ms" in queries


def test_import_signoz_dry_run_alerts() -> None:
    payload = _run_import("alerts")
    alerts = payload["alerts"]
    assert alerts["groups"] >= 3
    assert alerts["rules"] >= 4
    assert alerts["status"] == "dry-run"
