"""E-32 federated MCP contract."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "docs" / "FEDERATED_MCP.md"
VALUES = REPO_ROOT / "deploy" / "helm" / "hybrid-rag" / "values.yaml"
CONFIGMAP = REPO_ROOT / "deploy" / "helm" / "hybrid-rag" / "templates" / "configmap-env.yaml"


def test_federated_mcp_doc_exists() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "E-32" in text
    assert "OQ3" in text
    assert "FEDERATED_MCP_ENABLED" in text


def test_federated_catalog_module_exists() -> None:
    path = REPO_ROOT / "query" / "app" / "federated_catalog.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "FederatedCatalogStore" in text
    assert "peer_endpoints" in text


def test_catalog_store_wraps_federated_when_enabled() -> None:
    text = (REPO_ROOT / "query" / "app" / "catalog_store.py").read_text(encoding="utf-8")
    assert "FederatedCatalogStore" in text
    assert "federated_mcp_enabled" in text


def test_helm_values_define_federated_mcp_block() -> None:
    text = VALUES.read_text(encoding="utf-8")
    assert "federatedMcp:" in text


def test_configmap_emits_federated_mcp_env() -> None:
    cm = CONFIGMAP.read_text(encoding="utf-8")
    assert "FEDERATED_MCP_ENABLED" in cm
    assert "MCP_REGION" in cm
    assert "MCP_PEER_ENDPOINTS_JSON" in cm
