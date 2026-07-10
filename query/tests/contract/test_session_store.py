"""Session store principal isolation."""

from __future__ import annotations

from app.session_store import InMemorySessionStore


def test_session_principal_isolation() -> None:
    store = InMemorySessionStore()
    created = store.create_session(tenant_id="acme", principal="user:alice", title="A")
    session_id = created["session_id"]
    assert store.get_session(session_id, tenant_id="acme", principal="user:bob") is None
    assert store.get_session(session_id, tenant_id="acme", principal="user:alice") is not None


def test_append_turn_increments_messages() -> None:
    store = InMemorySessionStore()
    created = store.create_session(tenant_id="acme", principal="user:alice")
    session_id = created["session_id"]
    store.append_turn(
        session_id,
        tenant_id="acme",
        principal="user:alice",
        user_content="hello",
        assistant_content="hi",
    )
    messages = store.get_history(session_id, tenant_id="acme", principal="user:alice")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
