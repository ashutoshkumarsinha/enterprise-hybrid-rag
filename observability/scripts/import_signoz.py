#!/usr/bin/env python3
"""Import SigNoz dashboards and alert rules from repo stubs (E-23).

Dry-run (default) validates stub JSON and prints transformed payloads.
Apply mode POSTs dashboards to SigNoz query-service when credentials are set.

Environment:
  SIGNOZ_API_URL   Base URL (e.g. http://localhost:8080)
  SIGNOZ_API_KEY   API key for SIGNOZ-API-KEY header (optional in dev)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

REPO_OBS = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_OBS / "dashboards"
ALERTS_FILE = REPO_OBS / "alerts" / "signoz-rules.yaml"
ALERT_NAME_RE = re.compile(r"^\s+- alert:\s+(\S+)", re.MULTILINE)
GROUP_NAME_RE = re.compile(r"^\s+- name:\s+(\S+)", re.MULTILINE)
SIGNOZ_DASHBOARD_STUBS = (
    "signoz-query-latency.json",
    "signoz-ingest-throughput.json",
)


def _panel_type(stub_type: str) -> str:
    if stub_type == "stat":
        return "value"
    return "graph"


def stub_to_signoz_dashboard(stub: dict[str, Any]) -> dict[str, Any]:
    """Transform hybrid-rag stub JSON into SigNoz PostableDashboard layout."""
    widgets: list[dict[str, Any]] = []
    layout: list[dict[str, Any]] = []
    for index, panel in enumerate(stub.get("panels", [])):
        widget_id = str(uuid.uuid4())
        promql = panel.get("query", "")
        widgets.append(
            {
                "id": widget_id,
                "title": panel.get("title", f"Panel {index + 1}"),
                "description": stub.get("description", ""),
                "panelTypes": _panel_type(panel.get("type", "graph")),
                "query": {
                    "queryType": "promql",
                    "promql": [
                        {
                            "name": "A",
                            "query": promql,
                            "legend": "",
                            "disabled": False,
                        }
                    ],
                },
            }
        )
        layout.append(
            {
                "h": 8,
                "i": widget_id,
                "moved": False,
                "static": False,
                "w": 6,
                "x": (index % 2) * 6,
                "y": (index // 2) * 8,
            }
        )
    return {
        "title": stub.get("title", "Hybrid RAG Dashboard"),
        "description": stub.get("description", ""),
        "tags": ["hybrid-rag", stub.get("spec_version", "hybrid-rag-obs")],
        "version": "v5",
        "layout": layout,
        "widgets": widgets,
        "panelMap": {},
        "variables": {},
    }


def load_dashboard_stubs() -> list[tuple[str, dict[str, Any]]]:
    stubs: list[tuple[str, dict[str, Any]]] = []
    for name in SIGNOZ_DASHBOARD_STUBS:
        path = DASHBOARD_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"dashboard stub missing: {path}")
        stubs.append((name, json.loads(path.read_text(encoding="utf-8"))))
    return stubs


def load_alert_rules() -> dict[str, Any]:
    if not ALERTS_FILE.is_file():
        raise FileNotFoundError(f"alerts file missing: {ALERTS_FILE}")
    text = ALERTS_FILE.read_text(encoding="utf-8")
    return {
        "groups": GROUP_NAME_RE.findall(text),
        "rules": ALERT_NAME_RE.findall(text),
        "raw": text,
    }


def _api_request(
    method: str,
    url: str,
    *,
    api_key: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["SIGNOZ-API-KEY"] = api_key
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, dict) and payload.get("status") == "success":
        return payload.get("data", payload)
    return payload if isinstance(payload, dict) else {"result": payload}


def import_dashboards(*, apply: bool, api_url: str, api_key: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, stub in load_dashboard_stubs():
        dashboard = stub_to_signoz_dashboard(stub)
        entry: dict[str, Any] = {
            "file": name,
            "title": dashboard["title"],
            "widgets": len(dashboard["widgets"]),
        }
        if apply:
            created = _api_request(
                "POST",
                f"{api_url.rstrip('/')}/api/v1/dashboards",
                api_key=api_key,
                body=dashboard,
            )
            entry["id"] = created.get("id") if isinstance(created, dict) else None
            entry["status"] = "created"
        else:
            entry["status"] = "dry-run"
            entry["payload"] = dashboard
        results.append(entry)
    return results


def import_alerts(*, apply: bool) -> dict[str, Any]:
    rules_doc = load_alert_rules()
    result: dict[str, Any] = {
        "status": "dry-run" if not apply else "manual",
        "groups": len(rules_doc["groups"]),
        "rules": len(rules_doc["rules"]),
        "file": str(ALERTS_FILE.relative_to(REPO_OBS.parent)),
    }
    if apply:
        result["note"] = (
            "SigNoz alert rules require UI or Terraform provider import; "
            "export validated for operator handoff."
        )
    else:
        result["rule_names"] = rules_doc["rules"]
        result["group_names"] = rules_doc["groups"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import SigNoz dashboards and alerts (E-23)")
    parser.add_argument(
        "target",
        choices=("dashboards", "alerts", "all"),
        nargs="?",
        default="all",
        help="What to import (default: all)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="POST dashboards to SIGNOZ_API_URL (default: dry-run)",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("SIGNOZ_API_URL", "http://localhost:8080"),
        help="SigNoz query-service base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SIGNOZ_API_KEY", ""),
        help="SigNoz API key (SIGNOZ-API-KEY header)",
    )
    args = parser.parse_args(argv)

    output: dict[str, Any] = {"apply": args.apply}
    try:
        if args.target in ("dashboards", "all"):
            output["dashboards"] = import_dashboards(
                apply=args.apply,
                api_url=args.api_url,
                api_key=args.api_key,
            )
        if args.target in ("alerts", "all"):
            output["alerts"] = import_alerts(apply=args.apply)
    except (FileNotFoundError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print(f"import_signoz failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
