"""load_test.py wrapper tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from benchmarks.load_test import (
    _parse_duration_seconds,
    build_k6_command,
    build_locust_command,
    run_http_backend,
)

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def test_parse_duration() -> None:
    assert _parse_duration_seconds("30s") == 30
    assert _parse_duration_seconds("2m") == 120
    assert _parse_duration_seconds("1h") == 3600


def test_build_k6_command() -> None:
    cmd, env = build_k6_command(
        url="http://localhost:8010",
        concurrency=50,
        duration="30m",
        tenant_id="acme",
        collection_id="payments-api",
    )
    assert cmd[0] == "k6"
    assert str(BENCHMARKS / "k6" / "research_stream.js") in cmd[-1]
    assert env["VUS"] == "50"
    assert env["DURATION"] == "30m"


def test_build_locust_command() -> None:
    cmd, _env = build_locust_command(
        url="http://localhost:8010",
        concurrency=50,
        duration="30m",
        tenant_id="acme",
        collection_id="payments-api",
    )
    assert cmd[0] == "locust"
    assert "--headless" in cmd
    assert "-u" in cmd and "50" in cmd


def test_dry_run_k6() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(BENCHMARKS / "load_test.py"),
            "--backend",
            "k6",
            "--dry-run",
            "--concurrency",
            "10",
            "--duration",
            "5m",
        ],
        cwd=BENCHMARKS.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["backend"] == "k6"
    assert payload["command"][0] == "k6"


def test_http_backend_zero_requests() -> None:
    summary = run_http_backend(
        url="http://127.0.0.1:1",
        concurrency=1,
        requests=0,
        query="test",
        timeout=0.1,
    )
    assert summary["requests"] == 0
    assert summary["errors"] == 0
