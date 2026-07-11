"""E-16 ACL grant API contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR = REPO_ROOT / "ingest" / "app" / "orchestrator.py"
ADMIN_API = REPO_ROOT / "ingest" / "docs" / "ADMIN_API.md"

ACL_ROUTES = (
    '"/admin/acl/grants"',
    '"/admin/acl/grants/{grant_id}"',
    '"/admin/collections/{tenant_id}/{collection_id}/default_acl"',
)


def test_acl_handlers_and_store_exist() -> None:
    assert (REPO_ROOT / "ingest" / "app" / "acl_store.py").is_file()
    assert (REPO_ROOT / "ingest" / "app" / "acl_handlers.py").is_file()


def test_orchestrator_wires_acl_routes() -> None:
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert "create_acl_grant" in text
    assert "list_acl_grants" in text
    assert "delete_acl_grant" in text
    assert "patch_collection_default_acl" in text
    for route in ACL_ROUTES:
        assert route in text


def test_acl_grant_publishes_acl_changed_event() -> None:
    text = (REPO_ROOT / "ingest" / "app" / "acl_handlers.py").read_text(encoding="utf-8")
    assert "publish_acl_changed" in text


def test_admin_api_documents_acl_routes() -> None:
    text = ADMIN_API.read_text(encoding="utf-8")
    for fragment in ("/admin/acl/grants", "default_acl", "DELETE"):
        assert fragment in text
