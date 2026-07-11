"""Query retrieves corpus seeded in ingest chunk_payload shape."""

from __future__ import annotations

import hashlib
import uuid

import pytest

from app.client_factory import embed_query, retrieve_chunks, reset_clients
from tests.integration.seed_ingest_fixture import load_ingest_fixture, upsert_ingest_fixture


@pytest.fixture()
def seeded_corpus(live_stack_ready: None) -> dict:
    reset_clients()
    fixture = load_ingest_fixture()
    suffix = uuid.uuid4().hex[:8]
    fixture = {
        **fixture,
        "document_id": f"{fixture['document_id']}-{suffix}",
    }
    chunks = []
    for idx, chunk in enumerate(fixture["chunks"], start=1):
        row = dict(chunk)
        row["uuid"] = str(uuid.uuid4())
        row["document_id"] = fixture["document_id"]
        row["chunk_index"] = idx
        row["content_hash"] = hashlib.sha256(row["text"].encode("utf-8")).hexdigest()
        chunks.append(row)
    fixture["chunks"] = chunks
    upsert_ingest_fixture(fixture)
    yield fixture
    reset_clients()


def test_query_retrieves_ingest_fixture(seeded_corpus: dict) -> None:
    query = seeded_corpus["query"]
    dense, sparse = embed_query(query)
    state = {
        "query": query,
        "tenant_id": seeded_corpus["tenant_id"],
        "collection_id": seeded_corpus["collection_id"],
        "document_id": seeded_corpus["document_id"],
        "query_dense_vector": dense,
        "query_sparse_vector": sparse,
    }
    chunks = retrieve_chunks(state)
    texts = " ".join(chunk.get("text", "") for chunk in chunks)
    assert seeded_corpus["expected_phrase"] in texts


def test_ingest_fixture_tenant_scope(seeded_corpus: dict) -> None:
    query = seeded_corpus["expected_phrase"]
    dense, sparse = embed_query(query)
    wrong_tenant = retrieve_chunks(
        {
            "query": query,
            "tenant_id": "nonexistent-tenant",
            "collection_id": seeded_corpus["collection_id"],
            "query_dense_vector": dense,
            "query_sparse_vector": sparse,
        }
    )
    assert wrong_tenant == []
