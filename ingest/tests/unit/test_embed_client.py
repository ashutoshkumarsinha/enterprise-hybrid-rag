"""Embed client deterministic stub vectors."""

from __future__ import annotations

import os

from app.clients.embed import EmbedClient


def test_stub_embed_dimension() -> None:
    os.environ["EMBED_STUB"] = "true"
    client = EmbedClient(dimension=16)
    vec = client.embed("hello world")
    assert len(vec) == 16
    assert client.embed("hello world") == vec


def test_embed_batch_stub() -> None:
    os.environ["EMBED_STUB"] = "true"
    client = EmbedClient(dimension=8)
    vectors = client.embed_batch(["alpha", "beta"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 8


def test_sparse_tokens() -> None:
    client = EmbedClient()
    sparse = client.sparse_from_text("api key rotation")
    assert len(sparse["indices"]) == 3
    assert len(sparse["values"]) == 3
