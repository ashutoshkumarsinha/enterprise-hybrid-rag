"""INF-P3 Redis maxmemory compose contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = REPO_ROOT / "infra" / "compose" / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "infra" / ".env.example"


def test_redis_compose_sets_maxmemory() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "REDIS_MAXMEMORY" in text
    assert "REDIS_MAXMEMORY_POLICY" in text
    assert "--maxmemory" in text
    assert "--maxmemory-policy" in text
    assert "allkeys-lru" in text


def test_env_example_documents_redis_memory() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "REDIS_MAXMEMORY=256mb" in text
    assert "REDIS_MAXMEMORY_POLICY=allkeys-lru" in text
