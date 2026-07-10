"""MCP tool registry."""

from __future__ import annotations

from app.mcp_tools import list_tool_definitions, load_tool_input_schema


def test_list_tool_definitions_includes_research() -> None:
    names = {item["name"] for item in list_tool_definitions()}
    assert "research_documents" in names
    assert "create_conversation_session" in names


def test_research_schema_has_query() -> None:
    schema = load_tool_input_schema("research_documents")
    assert "query" in schema["properties"]
