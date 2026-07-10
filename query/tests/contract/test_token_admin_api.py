"""Admin token mint HTTP contract."""

from __future__ import annotations


def test_mint_token_response_shape(client) -> None:
    response = client.post(
        "/admin/mcp/tokens",
        json={
            "tenant_id": "acme",
            "principal": "user:alice",
            "role_template": "user",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"].startswith("rag_mcp_")
    assert "token_id" in body
    assert "mcp.research" in body["permissions"]


def test_authenticated_research_with_minted_token(client, admin_token: str) -> None:
    response = client.post(
        "/mcp/tools/research_documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"query": "authenticated query"},
    )
    assert response.status_code == 200
