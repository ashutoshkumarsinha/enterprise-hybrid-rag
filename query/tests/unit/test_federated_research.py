"""Unit tests for federated research merge."""

from __future__ import annotations

from app.federated_research import merge_research_results


def test_merge_prefers_home_region_answer() -> None:
    local = {"answer_text": "local answer", "sources": [{"document_id": "a", "version_id": "v1"}]}
    peers = [
        {"region": "us-east-1", "answer_text": "home answer", "sources": []},
    ]
    merged = merge_research_results(
        local, peers, home_region="us-east-1", local_region="eu-west-1"
    )
    assert merged["answer_text"] == "home answer"


def test_merge_combines_sources() -> None:
    local = {"answer_text": "x", "sources": [{"document_id": "a", "version_id": "v1"}]}
    peers = [
        {
            "region": "us-east-1",
            "answer_text": "y",
            "sources": [{"document_id": "b", "version_id": "v1"}],
        },
    ]
    merged = merge_research_results(
        local, peers, home_region=None, local_region="eu-west-1"
    )
    assert len(merged["sources"]) == 2
