"""Full LangGraph pipeline against live stores and inference."""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest

from app.client_factory import get_chat_client
from app.rag_graph import run_rag_pipeline
from app.rag_state import RAGState


@pytest.fixture()
def live_pipeline_state() -> RAGState:
    return RAGState(
        query="How do I rotate API keys?",
        tenant_id=os.environ.get("DEFAULT_TENANT_ID", "dev"),
        collection_id=os.environ.get("LIVE_TEST_COLLECTION_ID", "payments-api"),
        explicit_scope=True,
        skip_supervisor=True,
        graph_enrich_enabled=True,
        timings_ms={},
        from_cache=False,
        abstained=False,
    )


def test_rag_pipeline_completes(live_pipeline_state: RAGState) -> None:
    final = asyncio.run(run_rag_pipeline(live_pipeline_state))
    timings = final.get("timings_ms") or {}
    assert "embed" in timings
    assert "retrieve" in timings
    assert "rerank" in timings
    assert "answer" in timings
    assert final.get("answer_text")
    assert get_chat_client().is_stub is False


def test_rag_pipeline_not_stub_answer(live_pipeline_state: RAGState) -> None:
    final = asyncio.run(run_rag_pipeline(live_pipeline_state))
    assert final.get("stub") is False


def test_research_stream_live_http(live_client, live_pipeline_state: RAGState) -> None:
    """POST /research/stream against in-process app with live backends."""
    response = live_client.post(
        "/research/stream",
        json={
            "query": live_pipeline_state["query"],
            "collection_id": live_pipeline_state.get("collection_id"),
            "tenant_id": live_pipeline_state.get("tenant_id"),
        },
    )
    assert response.status_code == 200
    body = response.text
    assert "data:" in body
    assert '"type": "done"' in body or '"type": "telemetry"' in body


def test_research_stream_running_container_when_configured(live_stack_ready) -> None:
    base = os.environ.get("QUERY_BASE_URL", "").rstrip("/")
    if not base:
        return
    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "POST",
            f"{base}/research/stream",
            json={"query": "Summarize the refund policy", "collection_id": "payments-api"},
        ) as response:
            assert response.status_code == 200
            chunks = list(response.iter_text())
    assert any("data:" in chunk for chunk in chunks)
