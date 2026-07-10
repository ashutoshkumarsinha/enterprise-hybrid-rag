"""Per-client live probes (Qdrant, inference, Redis, catalog)."""

from __future__ import annotations

from app.catalog_store import create_catalog_store
from app.client_factory import (
    get_chat_client,
    get_embed_client,
    get_neo4j_client,
    get_qdrant_client,
    get_reranker_client,
)
from app.query_cache import redis_healthcheck
from app.settings import get_settings


import os


def test_qdrant_live_probe() -> None:
    client = get_qdrant_client()
    assert client.is_stub is False
    assert client.healthcheck() is True


def test_inference_live_probes() -> None:
    assert get_embed_client().is_stub is False
    assert get_embed_client().healthcheck() is True
    assert get_chat_client().is_stub is False
    assert get_chat_client().healthcheck() is True
    assert get_reranker_client().is_stub is False
    assert get_reranker_client().healthcheck() is True


def test_neo4j_live_probe() -> None:
    client = get_neo4j_client()
    assert client.is_stub is False
    assert client.healthcheck() is True


def test_redis_live_probe() -> None:
    assert redis_healthcheck() is True


def test_catalog_live_probe() -> None:
    store = create_catalog_store(get_settings())
    assert store.healthcheck() is True


def test_embed_dimension_matches_env() -> None:
    dim = int(os.environ.get("EMBED_DIMENSION", "768"))
    vector = get_embed_client().embed("dimension probe")
    assert len(vector) == dim
