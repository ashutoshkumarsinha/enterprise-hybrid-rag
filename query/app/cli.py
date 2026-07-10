"""Operator CLI for hybrid-rag-query."""

from __future__ import annotations

import argparse
import json
import sys

from app.settings import get_settings
from app.token_store import create_token_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    mint = sub.add_parser("mint-mcp-token", help="Mint a bootstrap MCP access token")
    mint.add_argument("--tenant", required=True)
    mint.add_argument("--principal", required=True)
    mint.add_argument("--template", default="admin")
    mint.add_argument("--label", default=None)
    mint.add_argument("--expires-in-days", type=int, default=None)

    args = parser.parse_args(argv)
    if args.command == "mint-mcp-token":
        settings = get_settings()
        if not settings.allow_token_bootstrap:
            print("Set ALLOW_TOKEN_BOOTSTRAP=true to mint via CLI", file=sys.stderr)
            return 1
        store = create_token_store(settings)
        result = store.mint(
            tenant_id=args.tenant,
            principal=args.principal,
            label=args.label,
            role_template=args.template,
            expires_in_days=args.expires_in_days,
            created_by="cli",
        )
        print(json.dumps(result, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
