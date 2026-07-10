"""MCP research_documents markdown contract."""

from __future__ import annotations


def test_research_documents_markdown_order(client) -> None:
    response = client.post(
        "/mcp/tools/research_documents",
        json={"query": "How do I rotate API keys?"},
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "**Sources:**" in markdown
    assert "MCP Search Telemetry" in markdown
    answer_pos = markdown.find("rotate")
    sources_pos = markdown.find("**Sources:**")
    telemetry_pos = markdown.find("MCP Search Telemetry")
    assert answer_pos < sources_pos < telemetry_pos


def test_research_documents_appends_session_history(client) -> None:
    created = client.post(
        "/mcp/tools/create_conversation_session",
        json={"title": "thread"},
    )
    session_id = created.json()["session_id"]
    client.post(
        "/mcp/tools/research_documents",
        json={"query": "first question", "session_id": session_id},
    )
    history = client.post(
        "/mcp/tools/get_conversation_history",
        json={"session_id": session_id},
    )
    messages = history.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["content"] == "first question"
