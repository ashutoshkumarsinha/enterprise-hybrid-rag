"""Nightly session retention prune — E-44 / sessions.max_age_days."""

from __future__ import annotations

import argparse
import json
import sys

from app.session_store import create_session_store
from app.settings import get_settings


def prune_sessions(*, max_age_days: int | None = None) -> dict[str, int]:
    settings = get_settings()
    days = max_age_days if max_age_days is not None else settings.session_max_age_days
    store = create_session_store(settings)
    return store.prune_stale_sessions(max_age_days=days)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prune stale conversation sessions (E-44)")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="Override SESSION_MAX_AGE_DAYS (default from settings)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report settings only; no DB writes")
    args = parser.parse_args(argv)

    settings = get_settings()
    days = args.max_age_days if args.max_age_days is not None else settings.session_max_age_days
    if args.dry_run:
        print(json.dumps({"dry_run": True, "max_age_days": days}))
        return 0

    if not settings.sessions_enabled:
        print("WARN: SESSIONS_ENABLED=false — prune skipped", file=sys.stderr)
        return 0

    result = prune_sessions(max_age_days=days)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
