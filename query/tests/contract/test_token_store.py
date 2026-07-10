"""Token store unit behavior."""

from __future__ import annotations

from app.token_store import InMemoryTokenStore, parse_mcp_token


def test_parse_mcp_token() -> None:
    token_id = "550e8400-e29b-41d4-a716-446655440000"
    parsed = parse_mcp_token(f"rag_mcp_{token_id}.secret123")
    assert parsed == (token_id, "secret123")


def test_mint_and_validate_roundtrip() -> None:
    store = InMemoryTokenStore()
    minted = store.mint(tenant_id="acme", principal="user:bob", role_template="user")
    row = store.validate_access_token(minted["access_token"])
    assert row is not None
    assert row["tenant_id"] == "acme"
    assert "mcp.research" in row["permissions"]


def test_revoke_invalidates_token() -> None:
    store = InMemoryTokenStore()
    minted = store.mint(tenant_id="acme", principal="user:bob", role_template="admin")
    token_id = minted["token_id"]
    store.revoke(token_id)
    assert store.validate_access_token(minted["access_token"]) is None
