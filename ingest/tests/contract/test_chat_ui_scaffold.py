"""E-18 mod-chat scaffold contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHAT_UI = REPO_ROOT / "chat-ui"
SERVER_ROUTES = CHAT_UI / "server" / "src" / "routes.ts"
QUERY_CLIENT = CHAT_UI / "server" / "src" / "queryClient.ts"
WEB_APP = CHAT_UI / "web" / "src" / "App.tsx"


def test_chat_ui_workspace_exists() -> None:
    assert (CHAT_UI / "package.json").is_file()
    assert (CHAT_UI / "server" / "package.json").is_file()
    assert (CHAT_UI / "web" / "package.json").is_file()


def test_bff_exposes_spec_endpoints() -> None:
    routes = SERVER_ROUTES.read_text(encoding="utf-8")
    client = QUERY_CLIENT.read_text(encoding="utf-8")
    for route in (
        '"/api/collections"',
        '"/api/collections/:collectionId/documents"',
        '"/api/threads"',
        '"/api/threads/:threadId/messages"',
    ):
        assert route in routes
    assert "/mcp/tools/create_conversation_session" in routes
    assert "/research/stream" in client


def test_web_has_scope_and_chat_components() -> None:
    text = WEB_APP.read_text(encoding="utf-8")
    assert "ScopeBar" in text
    assert "ChatViewport" in text
    assert "streamMessage" in text
