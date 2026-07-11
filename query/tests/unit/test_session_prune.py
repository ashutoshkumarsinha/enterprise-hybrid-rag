"""Session retention prune — E-44."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest

from app.session_prune import prune_sessions
from app.session_store import InMemorySessionStore


def test_prune_stale_sessions_soft_deletes_old_rows() -> None:
    store = InMemorySessionStore()
    created = store.create_session(tenant_id="acme", principal="user:alice", title="old")
    session_id = created["session_id"]
    store._sessions[session_id]["updated_at"] = (
        datetime.now(UTC) - timedelta(days=120)
    ).isoformat()
    fresh = store.create_session(tenant_id="acme", principal="user:alice", title="fresh")

    result = store.prune_stale_sessions(max_age_days=90)
    assert result["pruned"] == 1
    assert store.get_session(session_id, tenant_id="acme", principal="user:alice") is None
    assert store.get_session(fresh["session_id"], tenant_id="acme", principal="user:alice") is not None


def test_prune_sessions_cli_dry_run() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.session_prune", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["max_age_days"] == 90


def test_prune_sessions_in_memory_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemorySessionStore()
    old = store.create_session(tenant_id="acme", principal="user:bob")
    store._sessions[old["session_id"]]["updated_at"] = (
        datetime.now(UTC) - timedelta(days=100)
    ).isoformat()

    monkeypatch.setattr("app.session_prune.create_session_store", lambda settings=None: store)
    result = prune_sessions(max_age_days=90)
    assert result["pruned"] == 1
