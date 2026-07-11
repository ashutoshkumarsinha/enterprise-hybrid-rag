"""E-24 multi-region read replica story contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "docs" / "MULTI_REGION.md"
VALUES = REPO_ROOT / "deploy" / "helm" / "hybrid-rag" / "values.yaml"
CONFIGMAP = REPO_ROOT / "deploy" / "helm" / "hybrid-rag" / "templates" / "configmap-env.yaml"
SPEC = REPO_ROOT / "ENTERPRISE_HYBRID_RAG_SPEC.md"


def test_multi_region_doc_exists() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "E-24" in text
    assert "30s" in text or "30 s" in text
    assert "CATALOG_DSN_RO" in text
    assert "query_ro" in text


def test_spec_references_multi_region_expansion() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "E-24" in spec
    assert "catalog replication lag" in spec.lower() or "Multi-region" in spec


def test_helm_values_define_multi_region_block() -> None:
    text = VALUES.read_text(encoding="utf-8")
    assert "multiRegion:" in text
    assert "catalogReplicationLagSloSeconds" in text
    assert "readRegions" in text


def test_configmap_emits_multiregion_flags_when_enabled() -> None:
    cm = CONFIGMAP.read_text(encoding="utf-8")
    assert "MULTIREGION_ENABLED" in cm
    assert "CATALOG_REPLICATION_LAG_SLO_SECONDS" in cm
