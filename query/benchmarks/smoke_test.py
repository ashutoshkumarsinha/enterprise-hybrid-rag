#!/usr/bin/env python3
"""End-to-end smoke harness — health probes + /research/stream telemetry (§13.1).

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §13.2.1 · nightly tier
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

BENCHMARKS_DIR = Path(__file__).resolve().parent
REPO_QUERY_DIR = BENCHMARKS_DIR.parent
sys.path.insert(0, str(REPO_QUERY_DIR))


def _parse_sse_events(lines: list[str]) -> tuple[list[dict[str, Any]], int | None]:
    events: list[dict[str, Any]] = []
    ttft_ms: int | None = None
    start = time.perf_counter()
    for line in lines:
        if not line or not line.startswith("data: "):
            continue
        payload = json.loads(line[6:])
        events.append(payload)
        if payload.get("type") == "token" and ttft_ms is None:
            ttft_ms = int((time.perf_counter() - start) * 1000)
    return events, ttft_ms


def _summarize_stream(
    *,
    status: int,
    lines: list[str],
    started_at: float,
    ttft_ms: int | None,
) -> dict[str, Any]:
    events, parsed_ttft = _parse_sse_events(lines)
    ttft = ttft_ms if ttft_ms is not None else parsed_ttft
    total_ms = int((time.perf_counter() - started_at) * 1000)
    telemetry = next((event for event in events if event.get("type") == "telemetry"), {})
    error_event = next((event for event in events if event.get("type") == "error"), None)
    return {
        "status": status,
        "ok": status == 200 and not error_event and any(e.get("type") == "done" for e in events),
        "ttft_ms": ttft,
        "total_ms": total_ms,
        "event_types": [event.get("type") for event in events],
        "timings_ms": telemetry.get("timings_ms") or {},
        "stub": telemetry.get("stub"),
        "abstained": telemetry.get("abstained"),
        "error": error_event,
    }


def probe_health(url: str, *, path: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{url.rstrip('/')}{path}")
    latency_ms = int((time.perf_counter() - started) * 1000)
    body: dict[str, Any] = {}
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text[:200]}
    return {
        "status": response.status_code,
        "latency_ms": latency_ms,
        "ok": response.status_code == 200 and body.get("status") == "ok",
        "body": body,
    }


def run_research_stream_http(
    *,
    base_url: str,
    query: str,
    tenant_id: str,
    collection_id: str,
    timeout: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    ttft_ms: int | None = None
    lines: list[str] = []
    status = 0
    with httpx.Client(timeout=timeout) as client:
        with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/research/stream",
            json={
                "query": query,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
            },
        ) as response:
            status = response.status_code
            for line in response.iter_lines():
                if not line:
                    continue
                lines.append(line)
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    if payload.get("type") == "token" and ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - started) * 1000)
    return _summarize_stream(
        status=status,
        lines=lines,
        started_at=started,
        ttft_ms=ttft_ms,
    )


def run_research_stream_in_process(
    *,
    query: str,
    tenant_id: str,
    collection_id: str,
) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.catalog_store import create_catalog_store
    from app.mcp_server import app
    from app.session_store import InMemorySessionStore
    from app.settings import get_settings
    from app.token_store import InMemoryTokenStore

    settings = get_settings()
    app.state.settings = settings
    app.state.token_store = InMemoryTokenStore()
    app.state.session_store = InMemorySessionStore()
    app.state.catalog_store = create_catalog_store(settings)

    started = time.perf_counter()
    ttft_ms: int | None = None
    lines: list[str] = []
    status = 0
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/research/stream",
            json={
                "query": query,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
            },
        ) as response:
            status = response.status_code
            for line in response.iter_lines():
                if not line:
                    continue
                text = line.decode() if isinstance(line, bytes) else line
                lines.append(text)
                if text.startswith("data: "):
                    payload = json.loads(text[6:])
                    if payload.get("type") == "token" and ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - started) * 1000)
    return _summarize_stream(
        status=status,
        lines=lines,
        started_at=started,
        ttft_ms=ttft_ms,
    )


def run_e2e(args: argparse.Namespace) -> dict[str, Any]:
    query_url = (args.url or os.environ.get("QUERY_BASE_URL", "")).rstrip("/")
    ingest_url = (args.ingest_url or os.environ.get("INGEST_BASE_URL", "")).rstrip("/")
    use_in_process = args.in_process or not query_url

    report: dict[str, Any] = {
        "run_at": datetime.now(UTC).isoformat(),
        "mode": "in_process" if use_in_process else "http",
        "query_url": query_url or None,
        "ingest_url": ingest_url or None,
        "query": args.query,
        "tenant_id": args.tenant_id,
        "collection_id": args.collection_id,
    }

    if use_in_process:
        report["query_health"] = {
            "status": 200,
            "latency_ms": 0,
            "ok": True,
            "body": {"status": "ok", "in_process": True},
        }
        report["research_stream"] = run_research_stream_in_process(
            query=args.query,
            tenant_id=args.tenant_id,
            collection_id=args.collection_id,
        )
    else:
        report["query_health"] = probe_health(query_url, path="/healthz", timeout=args.timeout)
        if ingest_url:
            report["ingest_health"] = probe_health(
                ingest_url,
                path="/admin/healthz",
                timeout=args.timeout,
            )
        report["research_stream"] = run_research_stream_http(
            base_url=query_url,
            query=args.query,
            tenant_id=args.tenant_id,
            collection_id=args.collection_id,
            timeout=args.timeout,
        )

    report["passed"] = bool(
        report.get("query_health", {}).get("ok")
        and report.get("research_stream", {}).get("ok")
        and (not ingest_url or report.get("ingest_health", {}).get("ok"))
    )
    return report


def _check_thresholds(report: dict[str, Any], args: argparse.Namespace) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    stream = report.get("research_stream") or {}
    health = report.get("query_health") or {}

    if not health.get("ok"):
        failures.append("query /healthz not ok")
    ingest = report.get("ingest_health")
    if ingest is not None and not ingest.get("ok"):
        failures.append("ingest /admin/healthz not ok")
    if not stream.get("ok"):
        failures.append("research/stream did not complete with done event")

    ttft = stream.get("ttft_ms")
    total = stream.get("total_ms")
    if args.warn_ttft_ms is not None and ttft is not None and ttft > args.warn_ttft_ms:
        warnings.append(f"ttft {ttft}ms > warn {args.warn_ttft_ms}ms")
    if args.fail_ttft_ms is not None and ttft is not None and ttft > args.fail_ttft_ms:
        failures.append(f"ttft {ttft}ms > fail {args.fail_ttft_ms}ms")
    if args.warn_total_ms is not None and total is not None and total > args.warn_total_ms:
        warnings.append(f"total {total}ms > warn {args.warn_total_ms}ms")
    if args.fail_total_ms is not None and total is not None and total > args.fail_total_ms:
        failures.append(f"total {total}ms > fail {args.fail_total_ms}ms")
    return warnings, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E2E smoke harness for hybrid-rag-query")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end smoke (required)")
    parser.add_argument("--url", default=os.environ.get("QUERY_BASE_URL", ""))
    parser.add_argument("--ingest-url", default=os.environ.get("INGEST_BASE_URL", ""))
    parser.add_argument("--in-process", action="store_true", help="Use FastAPI TestClient (no HTTP)")
    parser.add_argument("--query", default="How do I rotate API keys?")
    parser.add_argument("--tenant-id", default=os.environ.get("DEFAULT_TENANT_ID", "dev"))
    parser.add_argument("--collection-id", default=os.environ.get("LIVE_TEST_COLLECTION_ID", "payments-api"))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", type=Path, default=BENCHMARKS_DIR / "last_smoke_e2e.json")
    parser.add_argument("--warn-ttft-ms", type=int, default=None)
    parser.add_argument("--fail-ttft-ms", type=int, default=None)
    parser.add_argument("--warn-total-ms", type=int, default=None)
    parser.add_argument("--fail-total-ms", type=int, default=None)
    args = parser.parse_args(argv)

    if not args.e2e:
        parser.error("--e2e is required")

    report = run_e2e(args)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

    warnings, failures = _check_thresholds(report, args)
    for msg in warnings:
        print(f"WARN: {msg}", file=sys.stderr)
    for msg in failures:
        print(f"FAIL: {msg}", file=sys.stderr)
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
