"""E-14 catalog migrations on disk."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "ingest" / "migrations"
MIGRATE = REPO_ROOT / "ingest" / "app" / "migrate.py"

REQUIRED_MIGRATIONS = (
    "001_catalog_v1.sql",
    "002_conversation_sessions_v1.sql",
    "003_mcp_access_tokens_v1.sql",
    "004_grant_query_roles_v1.sql",
)


def test_migrate_runner_exists() -> None:
    assert MIGRATE.is_file()


def test_all_catalog_migrations_present() -> None:
    for name in REQUIRED_MIGRATIONS:
        assert (MIGRATIONS / name).is_file(), f"missing migration {name}"


def test_makefile_exposes_migrate_target() -> None:
    text = (REPO_ROOT / "ingest" / "Makefile").read_text(encoding="utf-8")
    assert "migrate:" in text
    assert "app.migrate" in text
