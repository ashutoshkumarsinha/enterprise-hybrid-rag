"""smoke_test.py --e2e harness tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from benchmarks.smoke_test import _parse_sse_events, _summarize_stream

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def test_parse_sse_events_extracts_ttft() -> None:
    lines = [
        'data: {"type": "token", "text": "hello"}',
        'data: {"type": "telemetry", "timings_ms": {"total": 12}, "stub": true}',
        'data: {"type": "done"}',
    ]
    events, ttft = _parse_sse_events(lines)
    assert len(events) == 3
    assert events[0]["type"] == "token"
    assert ttft is not None


def test_summarize_stream_marks_ok_on_done() -> None:
    lines = [
        'data: {"type": "token", "text": "x"}',
        'data: {"type": "telemetry", "timings_ms": {"answer": 5}, "stub": true}',
        'data: {"type": "done"}',
    ]
    summary = _summarize_stream(
        status=200,
        lines=lines,
        started_at=__import__("time").perf_counter(),
        ttft_ms=None,
    )
    assert summary["ok"] is True
    assert summary["event_types"][-1] == "done"
    assert summary["timings_ms"]["answer"] == 5


def test_smoke_e2e_in_process() -> None:
    output = BENCHMARKS / "last_smoke_test.json"
    result = subprocess.run(
        [
            sys.executable,
            str(BENCHMARKS / "smoke_test.py"),
            "--e2e",
            "--in-process",
            "--output",
            str(output),
        ],
        cwd=BENCHMARKS.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["mode"] == "in_process"
    assert report["passed"] is True
    assert report["research_stream"]["ok"] is True
    assert "token" in report["research_stream"]["event_types"]
