"""LangSmith ingest tracing helpers (LG-5)."""

from __future__ import annotations

import os

from app.langsmith_config import ingest_traceable, langsmith_enabled, setup_langsmith


def test_langsmith_enabled_requires_key(monkeypatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    assert langsmith_enabled() is False

    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-test-key")
    assert langsmith_enabled() is True


def test_setup_langsmith_sets_project(monkeypatch) -> None:
    import app.langsmith_config as mod

    mod._CONFIGURED = False
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-test-key")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "hybrid-rag-ingest-test")

    setup_langsmith()

    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "hybrid-rag-ingest-test"


def test_ingest_traceable_preserves_callable() -> None:
    @ingest_traceable("ingest.test.span", run_type="chain")
    def sample(value: int) -> int:
        return value + 1

    assert sample(2) == 3
