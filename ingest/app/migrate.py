"""Catalog migration runner for hybrid-rag-ingest.

Spec: ingest/docs/MIGRATIONS.md · ENTERPRISE_HYBRID_RAG_SPEC.md §4.4.4.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
ADVISORY_LOCK_KEY = 742001


def _dsn() -> str:
    dsn = os.environ.get("CATALOG_DSN")
    if not dsn:
        raise SystemExit("CATALOG_DSN is required")
    return dsn


def _connect():
    import psycopg

    return psycopg.connect(_dsn())


def ensure_schema_migrations(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def applied_versions(cur) -> set[str]:
    ensure_schema_migrations(cur)
    cur.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def pending_files(applied: set[str]) -> list[Path]:
    files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    return [f for f in files if f.stem not in applied]


def apply_file(cur, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    cur.execute(sql)
    cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))


def migrate(*, dry_run: bool = False) -> list[str]:
    applied_new: list[str] = []
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
            applied = applied_versions(cur)
            pending = pending_files(applied)
            if dry_run:
                return [p.stem for p in pending]
            for path in pending:
                apply_file(cur, path)
                applied_new.append(path.stem)
            cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
        conn.commit()
    return applied_new


def status() -> dict[str, list[str]]:
    with _connect() as conn:
        with conn.cursor() as cur:
            applied = sorted(applied_versions(cur))
            pending = [p.stem for p in pending_files(set(applied))]
    return {"applied": applied, "pending": pending}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.migrate")
    parser.add_argument("--status", action="store_true", help="List applied and pending migrations")
    parser.add_argument("--dry-run", action="store_true", help="Print pending migrations only")
    args = parser.parse_args(argv)

    if args.status:
        import json

        print(json.dumps(status(), indent=2))
        return 0

    if args.dry_run:
        try:
            with _connect() as conn:
                with conn.cursor() as cur:
                    pending = [p.stem for p in pending_files(applied_versions(cur))]
        except Exception as exc:
            print(f"migrate dry-run failed: {exc}", file=sys.stderr)
            return 1
        for version in pending:
            print(version)
        return 0

    try:
        applied = migrate()
    except Exception as exc:
        print(f"migrate failed: {exc}", file=sys.stderr)
        return 1

    if applied:
        print(f"Applied: {', '.join(applied)}")
    else:
        print("No pending migrations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
