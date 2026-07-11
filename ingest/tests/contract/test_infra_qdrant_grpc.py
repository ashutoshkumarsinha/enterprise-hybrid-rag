"""INF-P5 Qdrant gRPC port and consumer env contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = REPO_ROOT / "infra" / "compose" / "docker-compose.yml"
QUERY_LIVE_ENV = REPO_ROOT / "query" / ".env.live.example"
INGEST_LIVE_ENV = REPO_ROOT / "ingest" / ".env.live.example"


def test_compose_exposes_qdrant_grpc_port() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert '"6334:6334"' in text or "6334:6334" in text


def test_live_env_examples_enable_grpc() -> None:
    for path in (QUERY_LIVE_ENV, INGEST_LIVE_ENV):
        text = path.read_text(encoding="utf-8")
        assert "QDRANT_GRPC_PORT=6334" in text
        assert "PREFER_QDRANT_GRPC=true" in text
