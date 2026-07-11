"""Optional LangSmith tracing for Celery ingest tasks."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, TypeVar

_CONFIGURED = False

F = TypeVar("F", bound=Callable[..., Any])


def setup_langsmith() -> None:
    """Enable LangSmith when LANGCHAIN_TRACING_V2=true and API key is set."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    if not langsmith_enabled():
        return

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_PROJECT", "hybrid-rag-ingest"))
    endpoint = os.environ.get("LANGCHAIN_ENDPOINT", "").strip()
    if endpoint:
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)

    _CONFIGURED = True


def langsmith_enabled() -> bool:
    tracing = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    api_key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    return tracing and bool(api_key)


def ingest_traceable(name: str, *, run_type: str = "chain") -> Callable[[F], F]:
    """Decorate ingest spans for LangSmith when tracing is configured (LG-5)."""

    def decorator(fn: F) -> F:
        from langsmith import traceable

        return traceable(name=name, run_type=run_type)(fn)

    return decorator
