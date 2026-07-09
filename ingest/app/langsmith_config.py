"""Optional LangSmith tracing for Celery ingest tasks."""

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

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_PROJECT", "hybrid-rag-ingest"))
    endpoint = os.environ.get("LANGCHAIN_ENDPOINT", "").strip()
    if endpoint:
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)

    _CONFIGURED = True
