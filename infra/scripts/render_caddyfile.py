#!/usr/bin/env python3
"""Render Caddyfile from infra.toml [caddy] section.

Usage:
  python render_caddyfile.py --config ../config/infra.toml
  python render_caddyfile.py --config ../config/infra.toml --write ../caddy/Caddyfile
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


def _reverse_proxy_lines(*, upstream: str, indent: str) -> list[str]:
    pad = indent
    inner = indent + "    "
    return [
        f"{pad}reverse_proxy {upstream} {{",
        f"{inner}flush_interval -1",
        f"{inner}header_up X-Forwarded-For {{remote_host}}",
        f"{inner}header_up X-Real-IP {{remote_host}}",
        f"{inner}header_up X-Forwarded-Proto {{scheme}}",
        f"{inner}transport http {{",
        f"{inner}    versions 1.1",
        f"{inner}}}",
        f"{pad}}}",
    ]


def _auth_gate_lines(*, indent: str, token: str) -> list[str]:
    return [
        f'{indent}@unauthorized {{',
        f'{indent}    not header Authorization "Bearer {token}"',
        f"{indent}}}",
        f'{indent}respond @unauthorized "Unauthorized" 401',
        "",
    ]


def render(caddy: dict) -> str:
    site = caddy.get("site_name", "localhost")
    email = caddy.get("email", "ops@example.com")
    tls = caddy.get("tls", False)
    mcp_path = caddy.get("mcp_path", "/mcp").rstrip("/")
    research_path = caddy.get("research_stream_path", "/research/stream")
    upstream = caddy.get("mcp_upstream", "127.0.0.1:8010")
    token = caddy.get("mcp_bearer_token", "")
    proxy_research = caddy.get("proxy_research_stream", True)

    lines = ["# Auto-generated — do not edit by hand", f"{site} {{"]
    if tls and site not in ("localhost", "127.0.0.1"):
        lines.append(f"    tls {email}")
    else:
        lines.append("    tls internal")

    lines.append("")
    lines.append(f"    handle_path {mcp_path}/* {{")
    if token:
        lines.extend(_auth_gate_lines(indent="        ", token=token))
    lines.extend(_reverse_proxy_lines(upstream=upstream, indent="        "))
    lines.append("    }")

    if proxy_research:
        lines.append("")
        lines.append(f"    handle {research_path} {{")
        if token:
            lines.extend(_auth_gate_lines(indent="        ", token=token))
        lines.extend(_reverse_proxy_lines(upstream=upstream, indent="        "))
        lines.append("    }")

    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--write", type=Path, default=None)
    args = parser.parse_args()

    data = tomllib.loads(args.config.read_text(encoding="utf-8"))
    caddy = data.get("caddy", {})
    if not caddy.get("proxy_mcp", True):
        print("# proxy_mcp disabled", file=sys.stderr)
        return 1

    content = render(caddy)
    if args.write:
        args.write.write_text(content, encoding="utf-8")
        print(f"wrote {args.write}")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
