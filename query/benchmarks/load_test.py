#!/usr/bin/env python3
"""Unified load/soak harness — HTTP probe or k6/Locust wrapper (§13.1, NFR-23).

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §13.1 · TL-09
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

BENCHMARKS_DIR = Path(__file__).resolve().parent
_DURATION_RE = re.compile(r"^(\d+)(s|m|h)$")


def _parse_duration_seconds(duration: str) -> int:
    match = _DURATION_RE.match(duration.strip())
    if not match:
        raise ValueError(f"invalid duration {duration!r}; use e.g. 30s, 30m, 2h")
    value, unit = int(match.group(1)), match.group(2)
    if unit == "s":
        return value
    if unit == "m":
        return value * 60
    return value * 3600


def _one_http_request(base_url: str, query: str, timeout: float) -> tuple[int, float]:
    start = time.perf_counter()
    status = 0
    with httpx.Client(timeout=timeout) as client:
        with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/research/stream",
            json={"query": query, "collection_id": "payments-api", "tenant_id": "dev"},
        ) as response:
            status = response.status_code
            for _ in response.iter_lines():
                pass
    return status, time.perf_counter() - start


def run_http_backend(
    *,
    url: str,
    concurrency: int,
    requests: int,
    query: str,
    timeout: float,
) -> dict[str, Any]:
    latencies: list[float] = []
    errors = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(_one_http_request, url, query, timeout)
            for _ in range(requests)
        ]
        for future in as_completed(futures):
            status, elapsed = future.result()
            latencies.append(elapsed)
            if status != 200:
                errors += 1
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    return {
        "backend": "http",
        "url": url,
        "requests": requests,
        "concurrency": concurrency,
        "errors": errors,
        "p50_s": round(statistics.median(latencies), 3) if latencies else 0,
        "p95_s": round(p95, 3),
        "max_s": round(max(latencies), 3) if latencies else 0,
    }


def build_k6_command(
    *,
    url: str,
    concurrency: int,
    duration: str,
    tenant_id: str,
    collection_id: str,
) -> tuple[list[str], dict[str, str]]:
    script = BENCHMARKS_DIR / "k6" / "research_stream.js"
    env = {
        **os.environ,
        "QUERY_URL": url.rstrip("/"),
        "VUS": str(concurrency),
        "DURATION": duration,
        "TENANT_ID": tenant_id,
        "COLLECTION_ID": collection_id,
    }
    cmd = ["k6", "run", str(script)]
    return cmd, env


def build_locust_command(
    *,
    url: str,
    concurrency: int,
    duration: str,
    tenant_id: str,
    collection_id: str,
) -> tuple[list[str], dict[str, str]]:
    locustfile = BENCHMARKS_DIR / "locust" / "locustfile.py"
    spawn_rate = max(1, concurrency // 10)
    env = {
        **os.environ,
        "TENANT_ID": tenant_id,
        "COLLECTION_ID": collection_id,
    }
    cmd = [
        "locust",
        "-f",
        str(locustfile),
        "--headless",
        "-u",
        str(concurrency),
        "-r",
        str(spawn_rate),
        "-t",
        duration,
        "--host",
        url.rstrip("/"),
    ]
    return cmd, env


def _run_subprocess(cmd: list[str], env: dict[str, str], backend: str) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    elapsed_s = round(time.perf_counter() - started, 3)
    summary: dict[str, Any] = {
        "backend": backend,
        "command": cmd,
        "exit_code": proc.returncode,
        "elapsed_s": elapsed_s,
    }
    if proc.stdout:
        summary["stdout_tail"] = proc.stdout[-2000:]
    if proc.stderr:
        summary["stderr_tail"] = proc.stderr[-2000:]
    return summary


def _check_failures(summary: dict[str, Any], *, fail_p95_s: float | None) -> list[str]:
    failures: list[str] = []
    if summary.get("exit_code", 0) != 0:
        failures.append(f"{summary.get('backend')} exited with code {summary['exit_code']}")
    if summary.get("errors", 0) > 0:
        failures.append(f"http errors={summary['errors']}")
    p95 = summary.get("p95_s")
    if fail_p95_s is not None and p95 is not None and p95 > fail_p95_s:
        failures.append(f"p95 {p95}s > fail {fail_p95_s}s")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load/soak wrapper — http, k6, or Locust")
    parser.add_argument("--backend", choices=["http", "k6", "locust"], default="http")
    parser.add_argument("--url", default=os.environ.get("QUERY_BASE_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--requests", type=int, default=20, help="HTTP backend only")
    parser.add_argument("--duration", default="30m", help="k6/Locust duration (e.g. 30m, 2h)")
    parser.add_argument("--query", default="Summarize the refund policy")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID", "acme-corp"))
    parser.add_argument("--collection-id", default=os.environ.get("COLLECTION_ID", "payments-api"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-p95-s", type=float, default=None)
    parser.add_argument("--output", type=Path, default=BENCHMARKS_DIR / "last_load_test.json")
    args = parser.parse_args(argv)

    if args.backend == "http":
        summary = run_http_backend(
            url=args.url,
            concurrency=args.concurrency,
            requests=args.requests,
            query=args.query,
            timeout=args.timeout,
        )
    elif args.backend == "k6":
        cmd, env = build_k6_command(
            url=args.url,
            concurrency=args.concurrency,
            duration=args.duration,
            tenant_id=args.tenant_id,
            collection_id=args.collection_id,
        )
        if args.dry_run:
            print(json.dumps({"backend": "k6", "command": cmd, "env": {k: env[k] for k in (
                "QUERY_URL", "VUS", "DURATION", "TENANT_ID", "COLLECTION_ID"
            )}}, indent=2))
            return 0
        if not shutil.which("k6"):
            print("FAIL: k6 not found on PATH", file=sys.stderr)
            return 2
        summary = _run_subprocess(cmd, env, "k6")
        summary["url"] = args.url
        summary["concurrency"] = args.concurrency
        summary["duration"] = args.duration
    else:
        cmd, env = build_locust_command(
            url=args.url,
            concurrency=args.concurrency,
            duration=args.duration,
            tenant_id=args.tenant_id,
            collection_id=args.collection_id,
        )
        if args.dry_run:
            print(json.dumps({"backend": "locust", "command": cmd}, indent=2))
            return 0
        if not shutil.which("locust"):
            print("FAIL: locust not found on PATH", file=sys.stderr)
            return 2
        summary = _run_subprocess(cmd, env, "locust")
        summary["url"] = args.url
        summary["concurrency"] = args.concurrency
        summary["duration"] = args.duration

    summary["run_at"] = datetime.now(UTC).isoformat()
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

    failures = _check_failures(summary, fail_p95_s=args.fail_p95_s)
    for msg in failures:
        print(f"FAIL: {msg}", file=sys.stderr)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
