"""SSE event type contract for /research/stream."""

from __future__ import annotations

import json


def test_sse_event_types(client) -> None:
    with client.stream(
        "POST",
        "/research/stream",
        json={"query": "latency budget?"},
    ) as response:
        assert response.status_code == 200
        types: list[str] = []
        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            types.append(payload["type"])
        assert types[0] == "token"
        assert "sources" in types
        assert "telemetry" in types
        assert types[-1] == "done"
        assert all(t in {"token", "sources", "telemetry", "done", "error"} for t in types)


def test_sse_token_uses_text_field(client) -> None:
    with client.stream(
        "POST",
        "/research/stream",
        json={"query": "hello"},
    ) as response:
        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            if payload.get("type") == "token":
                assert "text" in payload
                break
