"""LG-5 LangSmith span naming contract for ingest Celery + parser paths."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_batch_write_uses_spec_span_name() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "tasks.py").read_text(encoding="utf-8")
    assert "ingest_traceable" in text
    assert 'ingest_traceable("ingest.job.batch_write"' in text
    assert "def _execute_batch_write" in text


def test_parse_file_uses_spec_span_name() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "parsers" / "router.py").read_text(encoding="utf-8")
    assert 'ingest_traceable("ingest.parser.parse_file"' in text
    assert 'run_type="parser"' in text


def test_langsmith_config_exports_helpers() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "langsmith_config.py").read_text(encoding="utf-8")
    assert "def langsmith_enabled" in text
    assert "def ingest_traceable" in text
