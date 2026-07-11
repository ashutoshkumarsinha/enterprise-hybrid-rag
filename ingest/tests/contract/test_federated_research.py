"""Federated research + query quota suffix + mTLS contracts."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_federated_research_module_exists() -> None:
    text = (REPO_ROOT / "query/app/federated_research.py").read_text(encoding="utf-8")
    assert "merge_federated_research" in text
    assert "fetch_peer_research" in text
    assert "merge_research_results" in text


def test_mcp_handlers_wire_federated_research() -> None:
    text = (REPO_ROOT / "query/app/mcp_handlers.py").read_text(encoding="utf-8")
    assert "merge_federated_research" in text
    assert "federated_internal" in text


def test_query_quota_suffix_from_catalog_ro() -> None:
    text = (REPO_ROOT / "query/app/quota_store.py").read_text(encoding="utf-8")
    assert "get_qdrant_collection_suffix" in text
    assert "qdrant_collection_suffix" in text
    qcoll = (REPO_ROOT / "query/app/qdrant_collection.py").read_text(encoding="utf-8")
    assert "get_quota_store" in qcoll


def test_mtls_server_entrypoint() -> None:
    assert (REPO_ROOT / "query/app/server.py").is_file()
    assert (REPO_ROOT / "query/app/tls_config.py").is_file()
    text = (REPO_ROOT / "query/app/tls_config.py").read_text(encoding="utf-8")
    assert "uvicorn_ssl_kwargs" in text
    assert "MCP_MTLS_ENABLED" in text


def test_federated_mcp_doc_covers_research() -> None:
    doc = (REPO_ROOT / "docs/FEDERATED_MCP.md").read_text(encoding="utf-8")
    assert "research" in doc.lower()
    assert "FEDERATED_RESEARCH" in doc
