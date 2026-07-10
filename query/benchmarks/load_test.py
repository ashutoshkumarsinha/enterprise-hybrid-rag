"""Lightweight HTTP load probe for /research/stream — §13.1.

Wraps concurrent POSTs; use k6 for full soak (benchmarks/k6/).
"""

from __future__ import annotations

import argparse
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


def _one_request(base_url: str, query: str, timeout: float) -> tuple[int, float]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Concurrent research/stream load probe")
    parser.add_argument("--url", default=os.environ.get("QUERY_BASE_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--query", default="Summarize the refund policy")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    latencies: list[float] = []
    errors = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(_one_request, args.url, args.query, args.timeout)
            for _ in range(args.requests)
        ]
        for future in as_completed(futures):
            status, elapsed = future.result()
            latencies.append(elapsed)
            if status != 200:
                errors += 1

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    print(
        {
            "url": args.url,
            "requests": args.requests,
            "concurrency": args.concurrency,
            "errors": errors,
            "p50_s": round(statistics.median(latencies), 3) if latencies else 0,
            "p95_s": round(p95, 3),
            "max_s": round(max(latencies), 3) if latencies else 0,
        }
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
