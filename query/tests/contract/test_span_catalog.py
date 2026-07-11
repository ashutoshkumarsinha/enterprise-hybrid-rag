"""E-06 OTel span catalog wired in application code."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "docs" / "releases" / "span_catalog.json"


def test_span_catalog_json_exists() -> None:
    assert CATALOG_PATH.is_file()


def test_query_telemetry_exports_catalog() -> None:
    from app.telemetry import QUERY_SPAN_CATALOG

    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    expected = set(data["query_spans"])
    assert QUERY_SPAN_CATALOG == expected


def test_rag_graph_wires_node_spans() -> None:
    text = (REPO_ROOT / "query" / "app" / "rag_graph.py").read_text(encoding="utf-8")
    for token in (
        "SPAN_RAG_NODE_CHECK_CACHE",
        "SPAN_RAG_NODE_SUPERVISOR",
        "SPAN_RAG_NODE_EMBED",
        "SPAN_RAG_NODE_RETRIEVE",
        "SPAN_RAG_NODE_ANSWER",
    ):
        assert token in text
    assert "SPAN_RAG_PIPELINE" in text
    assert "traced_rag_node" in text


def test_ingest_tasks_use_catalog_span_names() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "tasks.py").read_text(encoding="utf-8")
    assert "SPAN_JOB_BATCH_WRITE" in text
    assert "SPAN_CONNECTOR_SYNC" in text
    assert "SPAN_BEAT_CONNECTOR_SYNC" in text


def test_client_factory_wires_store_and_inference_spans() -> None:
    text = (REPO_ROOT / "query" / "app" / "client_factory.py").read_text(encoding="utf-8")
    assert "SPAN_INFERENCE_EMBED" in text
    assert "SPAN_INFERENCE_CHAT" in text
    assert "SPAN_STORE_QDRANT_RETRIEVE" in text
    assert "SPAN_STORE_NEO4J_READ" in text


def test_mcp_handlers_wire_session_spans() -> None:
    text = (REPO_ROOT / "query" / "app" / "mcp_handlers.py").read_text(encoding="utf-8")
    assert "SPAN_MCP_RESEARCH_DOCUMENTS" in text
    assert "SPAN_SESSION_LOAD_HISTORY" in text
    assert "SPAN_SESSION_APPEND_TURN" in text


def test_rbac_wires_authz_span() -> None:
    text = (REPO_ROOT / "query" / "app" / "rbac.py").read_text(encoding="utf-8")
    assert "SPAN_MCP_AUTHZ_CHECK" in text
