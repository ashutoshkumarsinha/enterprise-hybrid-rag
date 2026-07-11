#!/usr/bin/env python3
"""Chaos test suite automation — spec §13.1 monthly staging (E-26).

Dry-run validates scenario catalog for CI. --apply runs injections against a live stack.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = Path(__file__).resolve().parent / "scenarios.json"
REQUIRED_SCENARIO_IDS = {
    "redis_unavailable",
    "embed_timeout",
    "qdrant_slow",
    "vllm_restart",
    "ingest_flood",
}


def load_scenarios() -> dict[str, Any]:
    data = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    ids = {item["id"] for item in data.get("scenarios", [])}
    missing = REQUIRED_SCENARIO_IDS - ids
    if missing:
        raise ValueError(f"missing chaos scenarios: {sorted(missing)}")
    return data


def _compose_cmd(compose_file: str, *args: str) -> list[str]:
    path = ROOT / compose_file
    if not path.is_file():
        raise FileNotFoundError(f"compose file not found: {path}")
    return ["docker", "compose", "-f", str(path), *args]


def _run_compose_action(spec: dict[str, Any]) -> None:
    action = spec["action"]
    service = spec["service"]
    cmd = _compose_cmd(spec["compose_file"])
    if action == "pause":
        subprocess.run([*cmd, "pause", service], check=True, cwd=ROOT)
        return
    if action == "unpause":
        subprocess.run([*cmd, "unpause", service], check=True, cwd=ROOT)
        return
    if action == "stop":
        subprocess.run([*cmd, "stop", service], check=True, cwd=ROOT)
        return
    if action == "start":
        subprocess.run([*cmd, "start", service], check=True, cwd=ROOT)
        return
    if action == "restart":
        subprocess.run([*cmd, "restart", service], check=True, cwd=ROOT)
        return
    if action == "wait_healthy":
        timeout_s = int(spec.get("timeout_s", 120))
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            result = subprocess.run([*cmd, "ps", "--status", "running", "--services", service], cwd=ROOT)
            if result.returncode == 0:
                return
            time.sleep(2)
        raise TimeoutError(f"service {service} not healthy within {timeout_s}s")
    raise ValueError(f"unsupported compose action: {action}")


def _apply_compose_env(spec: dict[str, Any]) -> None:
    env = os.environ.copy()
    env.update({key: str(value) for key, value in spec.get("vars", {}).items()})
    cmd = _compose_cmd(spec["compose_file"], "up", "-d", spec["service"])
    subprocess.run(cmd, check=True, cwd=ROOT, env=env)


def inject_fault(spec: dict[str, Any]) -> None:
    if spec.get("type") == "compose_env":
        _apply_compose_env(spec)
        time.sleep(5)
        return
    _run_compose_action(spec)


def restore_fault(spec: dict[str, Any]) -> None:
    if spec.get("type") == "compose_env":
        _apply_compose_env(spec)
        return
    _run_compose_action(spec)


def probe_research_stream(query_url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    status = 0
    body_snippet = ""
    with httpx.Client(timeout=timeout) as client:
        try:
            with client.stream(
                "POST",
                f"{query_url.rstrip('/')}/research/stream",
                json={
                    "query": "What is the API rate limit?",
                    "tenant_id": "acme-corp",
                    "collection_id": "payments-api",
                },
            ) as response:
                status = response.status_code
                if status != 200:
                    body_snippet = response.text[:200]
                else:
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            body_snippet = line[6:][:200]
                            break
        except httpx.HTTPError as exc:
            return {"ok": False, "status": 0, "error": str(exc), "latency_ms": 0}
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {"ok": status == 200, "status": status, "latency_ms": latency_ms, "body_snippet": body_snippet}


def probe_health_query(query_url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{query_url.rstrip('/')}/healthz")
    latency_ms = int((time.perf_counter() - started) * 1000)
    body: dict[str, Any] = {}
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text[:200]}
    return {
        "ok": response.status_code == 200,
        "status": response.status_code,
        "latency_ms": latency_ms,
        "body": body,
    }


def probe_ingest_enqueue(ingest_url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{ingest_url.rstrip('/')}/collections/docs/sync",
            json={"tenant_id": "acme-corp", "collection_id": "docs", "connector": "s3"},
        )
    latency_ms = int((time.perf_counter() - started) * 1000)
    detail: dict[str, Any] = {}
    try:
        detail = response.json().get("detail", response.json())
    except Exception:
        detail = {"raw": response.text[:200]}
    code = detail.get("code") if isinstance(detail, dict) else None
    return {
        "ok": response.status_code in (200, 202, 503),
        "status": response.status_code,
        "latency_ms": latency_ms,
        "code": code,
        "detail": detail,
    }


def evaluate_probe(
    probe: dict[str, Any],
    *,
    query_url: str,
    ingest_url: str,
    timeout: float,
) -> dict[str, Any]:
    probe_type = probe["type"]
    if probe_type == "research_stream":
        result = probe_research_stream(query_url, timeout)
    elif probe_type == "health_query":
        result = probe_health_query(query_url, timeout)
    elif probe_type == "ingest_enqueue":
        result = probe_ingest_enqueue(ingest_url, timeout)
    else:
        raise ValueError(f"unknown probe type: {probe_type}")

    passed = True
    reasons: list[str] = []
    status = int(result.get("status", 0))

    if "expect_status" in probe and status != int(probe["expect_status"]):
        passed = False
        reasons.append(f"expected status {probe['expect_status']}, got {status}")
    if "expect_code" in probe and result.get("code") != probe["expect_code"]:
        passed = False
        reasons.append(f"expected code {probe['expect_code']}, got {result.get('code')}")
    allow_status = probe.get("allow_status")
    if allow_status is not None and status not in allow_status:
        passed = False
        reasons.append(f"status {status} not in allow_status {allow_status}")
    forbid_status = probe.get("forbid_status", [])
    if status in forbid_status:
        passed = False
        reasons.append(f"forbidden status {status}")

    return {"type": probe_type, "passed": passed, "reasons": reasons, "result": result}


def run_scenario(
    scenario: dict[str, Any],
    *,
    query_url: str,
    ingest_url: str,
    timeout: float,
    apply: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": scenario["id"],
        "title": scenario["title"],
        "expected": scenario["expected"],
        "applied": apply,
        "passed": True,
        "probes": [],
    }
    if apply:
        inject_fault(scenario["inject"])
        time.sleep(min(int(scenario.get("duration_s", 10)), 5))
    for probe in scenario.get("probes", []):
        evaluated = evaluate_probe(
            probe,
            query_url=query_url,
            ingest_url=ingest_url,
            timeout=timeout,
        )
        record["probes"].append(evaluated)
        if not evaluated["passed"]:
            record["passed"] = False
    if apply:
        restore_fault(scenario["restore"])
    return record


def validate_catalog() -> dict[str, Any]:
    data = load_scenarios()
    issues: list[str] = []
    for scenario in data["scenarios"]:
        inject = scenario.get("inject", {})
        compose_file = inject.get("compose_file")
        if compose_file and not (ROOT / compose_file).is_file():
            issues.append(f"{scenario['id']}: missing compose file {compose_file}")
        if not scenario.get("probes"):
            issues.append(f"{scenario['id']}: no probes defined")
    return {
        "ok": not issues,
        "scenario_count": len(data["scenarios"]),
        "scenario_ids": [s["id"] for s in data["scenarios"]],
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chaos suite — §13.1 staging (E-26)")
    parser.add_argument("--dry-run", action="store_true", help="Validate scenario catalog only")
    parser.add_argument("--apply", action="store_true", help="Run injections on live stack")
    parser.add_argument("--scenario", action="append", help="Run subset of scenario ids")
    parser.add_argument("--query-url", default=os.environ.get("QUERY_BASE_URL", "http://localhost:8010"))
    parser.add_argument("--ingest-url", default=os.environ.get("INGEST_BASE_URL", "http://localhost:8020"))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "query" / "benchmarks" / "last_chaos.json",
    )
    args = parser.parse_args(argv)

    catalog = validate_catalog()
    if not catalog["ok"]:
        print(json.dumps(catalog, indent=2))
        return 1

    if args.dry_run or not args.apply:
        print(json.dumps({"mode": "dry-run", **catalog}, indent=2))
        if args.dry_run:
            return 0

    data = load_scenarios()
    selected = {s["id"]: s for s in data["scenarios"]}
    if args.scenario:
        selected = {sid: selected[sid] for sid in args.scenario if sid in selected}

    report: dict[str, Any] = {
        "mode": "apply",
        "started_at": datetime.now(UTC).isoformat(),
        "query_url": args.query_url,
        "ingest_url": args.ingest_url,
        "scenarios": [],
        "passed": True,
    }
    for scenario in selected.values():
        record = run_scenario(
            scenario,
            query_url=args.query_url,
            ingest_url=args.ingest_url,
            timeout=args.timeout,
            apply=True,
        )
        report["scenarios"].append(record)
        if not record["passed"]:
            report["passed"] = False

    report["finished_at"] = datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
