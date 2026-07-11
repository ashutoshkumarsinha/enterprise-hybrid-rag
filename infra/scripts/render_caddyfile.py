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


def _reverse_proxy_lines(
    *,
    upstream: str,
    indent: str,
    mtls: dict | None = None,
) -> list[str]:
    pad = indent
    inner = indent + "    "
    lines = [
        f"{pad}reverse_proxy {upstream} {{",
        f"{inner}flush_interval -1",
        f"{inner}header_up X-Forwarded-For {{remote_host}}",
        f"{inner}header_up X-Real-IP {{remote_host}}",
        f"{inner}header_up X-Forwarded-Proto {{scheme}}",
        f"{inner}transport http {{",
        f"{inner}    versions 1.1",
    ]
    if mtls and mtls.get("enabled"):
        lines.append(f"{inner}    tls")
        if ca := mtls.get("upstream_ca"):
            lines.append(f"{inner}    tls_trust_pool file {ca}")
        cert = mtls.get("upstream_cert")
        key = mtls.get("upstream_key")
        if cert and key:
            lines.append(f"{inner}    tls_client_auth {cert} {key}")
    lines.extend([f"{inner}}}", f"{pad}}}"])
    return lines


def _site_tls_lines(caddy: dict, mtls: dict) -> list[str]:
    site = caddy.get("site_name", "localhost")
    tls = caddy.get("tls", False)
    email = caddy.get("email", "ops@example.com")

    if mtls.get("client_auth") and mtls.get("client_ca"):
        issuer = f"tls {email}" if tls and site not in ("localhost", "127.0.0.1") else "tls internal"
        return [
            f"    {issuer} {{",
            "        client_auth {",
            "            mode require_and_verify",
            f"            trust_pool file {mtls['client_ca']}",
            "        }",
            "    }",
        ]

    if tls and site not in ("localhost", "127.0.0.1"):
        return [f"    tls {email}"]
    return ["    tls internal"]


def _auth_gate_lines(*, indent: str, token: str) -> list[str]:
    return [
        f'{indent}@unauthorized {{',
        f'{indent}    not header Authorization "Bearer {token}"',
        f"{indent}}}",
        f'{indent}respond @unauthorized "Unauthorized" 401',
        "",
    ]


def render(caddy: dict, mtls: dict | None = None) -> str:
    site = caddy.get("site_name", "localhost")
    mcp_path = caddy.get("mcp_path", "/mcp").rstrip("/")
    research_path = caddy.get("research_stream_path", "/research/stream")
    upstream = caddy.get("mcp_upstream", "127.0.0.1:8010")
    token = caddy.get("mcp_bearer_token", "")
    proxy_research = caddy.get("proxy_research_stream", True)
    mtls = mtls or {}

    lines = ["# Auto-generated — do not edit by hand", f"{site} {{"]
    lines.extend(_site_tls_lines(caddy, mtls))

    lines.append("")
    lines.append(f"    handle_path {mcp_path}/* {{")
    if token:
        lines.extend(_auth_gate_lines(indent="        ", token=token))
    lines.extend(_reverse_proxy_lines(upstream=upstream, indent="        ", mtls=mtls))
    lines.append("    }")

    if proxy_research:
        lines.append("")
        lines.append(f"    handle {research_path} {{")
        if token:
            lines.extend(_auth_gate_lines(indent="        ", token=token))
        lines.extend(_reverse_proxy_lines(upstream=upstream, indent="        ", mtls=mtls))
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

    mtls = data.get("caddy", {}).get("mtls", {})
    content = render(caddy, mtls)
    if args.write:
        args.write.write_text(content, encoding="utf-8")
        print(f"wrote {args.write}")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
