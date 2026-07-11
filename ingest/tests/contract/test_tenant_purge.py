"""E-21 tenant purge API contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR = REPO_ROOT / "ingest" / "app" / "orchestrator.py"
TENANT_PURGE = REPO_ROOT / "ingest" / "app" / "tenant_purge.py"
MAKEFILE = REPO_ROOT / "ingest" / "Makefile"


def test_orchestrator_exposes_tenant_purge_route() -> None:
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert '"/admin/tenants/{tenant_id}/purge"' in text
    assert "ingest.tenant.purge" in text


def test_tenant_purge_orchestrates_all_stores() -> None:
    text = TENANT_PURGE.read_text(encoding="utf-8")
    for symbol in (
        "QdrantWriter",
        "Neo4jWriter",
        "MinioStore",
        "purge_tenant_dedup_keys",
        "publish_tenant_purged",
        "PurgeConfirmationRequired",
    ):
        assert symbol in text


def test_makefile_supports_purge_tenant_target() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "purge-tenant:" in text
    assert "app.tenant_purge" in text
