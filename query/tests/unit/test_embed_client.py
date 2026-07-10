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


def test_sparse_tokens() -> None:
    client = EmbedClient()
    sparse = client.sparse_from_text("api key rotation")
    assert len(sparse["indices"]) == 3
    assert len(sparse["values"]) == 3
