"""E-15 query_ro Postgres role grants — catalog read-only contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GRANTS_SQL = REPO_ROOT / "ingest" / "migrations" / "004_grant_query_roles_v1.sql"
POSTGRES_INIT = REPO_ROOT / "infra" / "scripts" / "postgres-init.sh"


def test_grants_migration_exists() -> None:
    assert GRANTS_SQL.is_file()


def test_query_ro_is_select_only() -> None:
    text = GRANTS_SQL.read_text(encoding="utf-8")
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO query_ro" in text
    ro_lines = [line for line in text.splitlines() if "query_ro" in line]
    for line in ro_lines:
        assert "INSERT" not in line
        assert "UPDATE" not in line
        assert "DELETE" not in line


def test_query_session_rw_can_write_conversation_tables() -> None:
    text = GRANTS_SQL.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_sessions TO query_session_rw" in text
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_messages TO query_session_rw" in text


def test_query_token_rw_cannot_delete_tokens() -> None:
    text = GRANTS_SQL.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE ON mcp_access_tokens TO query_token_rw" in text
    assert "DELETE ON mcp_access_tokens" not in text


def test_postgres_init_creates_query_roles() -> None:
    text = POSTGRES_INIT.read_text(encoding="utf-8")
    for role in ("query_ro", "query_session_rw", "query_token_rw", "ingest_rw"):
        assert role in text
