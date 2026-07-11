#!/usr/bin/env python3
"""Ingest throughput benchmark — mock + live embed path (platform §13).

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §13.1 · ingest/docs/PERFORMANCE.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BENCHMARKS_DIR = Path(__file__).resolve().parent
REPO_INGEST_DIR = BENCHMARKS_DIR.parent
sys.path.insert(0, str(REPO_INGEST_DIR))

from app.catalog_store import reset_catalog_store  # noqa: E402
from app.dedup_store import reset_dedup_store  # noqa: E402
from app.writers import write_chunks  # noqa: E402


def _synthetic_chunk(index: int, *, tenant_id: str, collection_id: str, document_id: str) -> dict[str, Any]:
    return {
        "uuid": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "document_id": document_id,
        "version_id": "v1",
        "title": "Benchmark Doc",
        "text": f"Benchmark chunk {index}: rotate API keys every 90 days in production.",
        "chunk_index": index,
        "type": "text",
        "tags": ["benchmark"],
        "source_system": "benchmark",
        "source_uri": f"benchmark://{document_id}/{index}",
        "references": [],
        "ingested_at": datetime.now(UTC).isoformat(),
        "content_hash": f"bench-{index:08d}",
    }


def _build_chunks(count: int, *, tenant_id: str, collection_id: str, document_id: str) -> list[dict[str, Any]]:
    return [
        _synthetic_chunk(i, tenant_id=tenant_id, collection_id=collection_id, document_id=document_id)
        for i in range(1, count + 1)
    ]


def _apply_mock_env() -> None:
    os.environ["INGEST_WRITE_STUB"] = "true"
    os.environ["EMBED_STUB"] = "true"
    os.environ["QDRANT_STUB"] = "true"
    os.environ["NEO4J_STUB"] = "true"
    os.environ["DEDUP_ENABLED"] = "false"


def _require_live_stack() -> None:
    for key in ("INGEST_WRITE_STUB", "EMBED_STUB"):
        if os.environ.get(key, "true").lower() in ("true", "1", "yes"):
            raise SystemExit(f"live-stack requested but {key} is still enabled")


def _run_benchmark(
    chunks: list[dict[str, Any]],
    *,
    batch_size: int,
    job_id: str | None = None,
) -> dict[str, Any]:
    validated = 0
    written = 0
    documents_recorded = 0
    batches = 0
    start = time.perf_counter()
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        result = write_chunks(batch, job_id=job_id)
        validated += int(result.get("validated", 0))
        written += int(result.get("written", 0))
        documents_recorded = int(result.get("documents_recorded", 0))
        batches += 1
    elapsed_s = max(time.perf_counter() - start, 1e-9)
    chunks_per_min = validated / elapsed_s * 60.0
    return {
        "chunk_count": len(chunks),
        "validated": validated,
        "written": written,
        "documents_recorded": documents_recorded,
        "batches": batches,
        "elapsed_s": round(elapsed_s, 4),
        "chunks_per_min": round(chunks_per_min, 2),
        "chunks_per_sec": round(validated / elapsed_s, 4),
    }


def _check_thresholds(
    metrics: dict[str, Any],
    *,
    warn_chunks_per_min: float | None,
    fail_chunks_per_min: float | None,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    rate = float(metrics.get("chunks_per_min", 0))
    if warn_chunks_per_min is not None and rate < warn_chunks_per_min:
        warnings.append(f"chunks_per_min {rate:.2f} < warn {warn_chunks_per_min}")
    if fail_chunks_per_min is not None and rate < fail_chunks_per_min:
        failures.append(f"chunks_per_min {rate:.2f} < fail {fail_chunks_per_min}")
    return warnings, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest throughput benchmark")
    parser.add_argument("--mock", action="store_true", help="Stub stores; synthetic chunks only")
    parser.add_argument("--chunks", type=int, default=None, help="Synthetic chunk count")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--tenant-id", default="bench-tenant")
    parser.add_argument("--collection-id", default="bench-collection")
    parser.add_argument("--document-id", default="bench-doc")
    parser.add_argument("--warn-chunks-per-min", type=float, default=None)
    parser.add_argument("--fail-chunks-per-min", type=float, default=None)
    parser.add_argument("--output", type=Path, default=BENCHMARKS_DIR / "last_ingest_run.json")
    parser.add_argument("--live-stack", action="store_true")
    args = parser.parse_args(argv)

    mock = args.mock or not args.live_stack
    if args.live_stack or os.environ.get("LIVE_STACK", "").lower() in ("1", "true", "yes"):
        mock = False
        _require_live_stack()
    else:
        _apply_mock_env()

    chunk_count = args.chunks
    if chunk_count is None:
        chunk_count = 500 if mock else 8

    reset_dedup_store()
    reset_catalog_store()

    chunks = _build_chunks(
        chunk_count,
        tenant_id=args.tenant_id,
        collection_id=args.collection_id,
        document_id=args.document_id,
    )
    metrics = _run_benchmark(chunks, batch_size=max(args.batch_size, 1))
    summary = {
        "run_at": datetime.now(UTC).isoformat(),
        "mode": "mock" if mock else "live",
        "tenant_id": args.tenant_id,
        "collection_id": args.collection_id,
        "document_id": args.document_id,
        "batch_size": args.batch_size,
        **metrics,
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

    warnings, failures = _check_thresholds(
        metrics,
        warn_chunks_per_min=args.warn_chunks_per_min,
        fail_chunks_per_min=args.fail_chunks_per_min,
    )
    for msg in warnings:
        print(f"WARN: {msg}", file=sys.stderr)
    for msg in failures:
        print(f"FAIL: {msg}", file=sys.stderr)
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
