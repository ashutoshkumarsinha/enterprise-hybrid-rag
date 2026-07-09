"""LangSmith tracing bootstrap for hybrid-rag-query (LangGraph runs)."""

from __future__ import annotations

import os

_CONFIGURED = False


def setup_langsmith() -> None:
    """Enable LangSmith when LANGCHAIN_TRACING_V2=true and API key is set."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    tracing = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    api_key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    if not tracing or not api_key:
        return

    # LangGraph / LangChain auto-export runs when these env vars are set.
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    project = os.environ.get("LANGCHAIN_PROJECT", "hybrid-rag-query")
    os.environ.setdefault("LANGCHAIN_PROJECT", project)
    endpoint = os.environ.get("LANGCHAIN_ENDPOINT", "").strip()
    if endpoint:
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)

    _CONFIGURED = True


def langsmith_enabled() -> bool:
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes") and bool(
        os.environ.get("LANGCHAIN_API_KEY", "").strip()
    )
