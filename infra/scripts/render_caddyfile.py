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


def render(caddy: dict) -> str:
    site = caddy.get("site_name", "localhost")
    email = caddy.get("email", "ops@example.com")
    tls = caddy.get("tls", False)
    mcp_path = caddy.get("mcp_path", "/mcp").rstrip("/")
    upstream = caddy.get("mcp_upstream", "127.0.0.1:8010")
    token = caddy.get("mcp_bearer_token", "")

    lines = ["# Auto-generated — do not edit by hand", f"{site} {{"]
    if tls and site not in ("localhost", "127.0.0.1"):
        lines.append(f"    tls {email}")
    else:
        lines.append("    tls internal")

    if token:
        lines.extend(
            [
                f"    handle_path {mcp_path}/* {{",
                '        @unauthorized {',
                f'            not header Authorization "Bearer {token}"',
                "        }",
                '        respond @unauthorized "Unauthorized" 401',
                "",
            ]
        )
    else:
        lines.append(f"    handle_path {mcp_path}/* {{")

    lines.extend(
        [
            f"        reverse_proxy {upstream} {{",
            "            flush_interval -1",
            "            header_up X-Forwarded-For {remote_host}",
            "            header_up X-Real-IP {remote_host}",
            "            header_up X-Forwarded-Proto {scheme}",
            "            transport http {",
            "                versions 1.1",
            "            }",
            "        }",
            "    }",
            "}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--write", type=Path, default=None)
    args = parser.parse_args()

    data = tomllib.loads(args.config.read_text())
    caddy = data.get("caddy", {})
    if not caddy.get("proxy_mcp", True):
        print("# proxy_mcp disabled", file=sys.stderr)
        return 1

    content = render(caddy)
    if args.write:
        args.write.write_text(content)
        print(f"wrote {args.write}")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
