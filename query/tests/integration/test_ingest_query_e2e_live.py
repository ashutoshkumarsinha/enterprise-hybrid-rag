"""End-to-end ingest write then query retrieval (live stack)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from app.client_factory import embed_query, retrieve_chunks, reset_clients

_REPO_ROOT = Path(__file__).resolve().parents[3]
_INGEST_ROOT = _REPO_ROOT / "ingest"
_FIXTURE = _INGEST_ROOT / "tests" / "fixtures" / "chunks" / "e2e-api-keys.json"


def _ingest_write_chunks(chunks: list[dict]) -> dict:
    """Run ingest write_chunks in a subprocess (package boundary)."""
    payload = json.dumps(chunks)
    code = """
import json, os, sys
sys.path.insert(0, os.getcwd())
from app.dedup_store import reset_dedup_store
from app.writers import write_chunks
os.environ.setdefault("INGEST_WRITE_STUB", "false")
os.environ.setdefault("DEDUP_ENABLED", "false")
reset_dedup_store()
chunks = json.loads(sys.argv[1])
print(json.dumps(write_chunks(chunks)))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code, payload],
        cwd=str(_INGEST_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(f"ingest write failed: {proc.stderr}")
    return json.loads(proc.stdout.strip())


@pytest.fixture()
def ingest_written_corpus(live_stack_ready: None) -> dict:
    if not _INGEST_ROOT.is_dir():
        pytest.skip("ingest sub-project not present")
    reset_clients()
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    suffix = uuid.uuid4().hex[:8]
    data["document_id"] = f"{data['document_id']}-{suffix}"
    chunks = []
    for idx, chunk in enumerate(data["chunks"], start=1):
        row = dict(chunk)
        row["uuid"] = str(uuid.uuid4())
        row["document_id"] = data["document_id"]
        row["chunk_index"] = idx
        row["content_hash"] = hashlib.sha256(row["text"].encode("utf-8")).hexdigest()
        chunks.append(row)
    data["chunks"] = chunks
    result = _ingest_write_chunks(chunks)
    assert result["written"] == len(chunks)
    yield data
    reset_clients()


def test_ingest_write_then_query_retrieve(ingest_written_corpus: dict) -> None:
    query = ingest_written_corpus["query"]
    dense, sparse = embed_query(query)
    chunks = retrieve_chunks(
        {
            "query": query,
            "tenant_id": ingest_written_corpus["tenant_id"],
            "collection_id": ingest_written_corpus["collection_id"],
            "document_id": ingest_written_corpus["document_id"],
            "query_dense_vector": dense,
            "query_sparse_vector": sparse,
        }
    )
    body = " ".join(c.get("text", "") for c in chunks)
    assert ingest_written_corpus["expected_phrase"] in body
