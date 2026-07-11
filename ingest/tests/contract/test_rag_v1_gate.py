"""rag-v1.0 release gate contract."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE = REPO_ROOT / "docs" / "releases" / "rag_v1_gate.json"
VALIDATE = REPO_ROOT / "scripts" / "validate_rag_v1.sh"


def test_rag_v1_gate_manifest_exists() -> None:
    assert GATE.is_file()
    data = json.loads(GATE.read_text(encoding="utf-8"))
    assert data["target_tag"] == "rag-v1.0"
    assert len(data["automated_gates"]) >= 5


def test_rag_v1_validate_script_exists() -> None:
    assert VALIDATE.is_file()


def test_oq_and_inf_docs_on_disk() -> None:
    paths = [
        "docs/MANAGED_STORES.md",
        "infra/docs/SCALE_OUT.md",
        "infra/docs/KEYCLOAK.md",
        "ingest/migrations/005_tenant_qdrant_suffix_v1.sql",
        "ingest/app/otel_metrics.py",
        "ingest/app/connectors/google_drive.py",
    ]
    for rel in paths:
        assert (REPO_ROOT / rel).is_file(), rel


def test_quota_store_exposes_qdrant_suffix() -> None:
    text = (REPO_ROOT / "ingest/app/quota_store.py").read_text(encoding="utf-8")
    assert "qdrant_collection_suffix" in text
    assert "get_qdrant_collection_suffix" in text
