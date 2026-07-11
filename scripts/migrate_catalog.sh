#!/usr/bin/env bash
# Apply catalog migrations from the host (rewrites Docker hostnames → 127.0.0.1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INGEST_DIR="$ROOT/ingest"
PY="${INGEST_DIR}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi

# Load ingest/.env when present (passwords, DSN template).
if [[ -f "$INGEST_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$INGEST_DIR/.env"
  set +a
fi

# Prefer explicit host DSN; else rewrite docker service names for host execution.
if [[ -n "${CATALOG_DSN_HOST:-}" ]]; then
  export CATALOG_DSN="$CATALOG_DSN_HOST"
elif [[ -n "${CATALOG_DSN:-}" ]]; then
  export CATALOG_DSN="${CATALOG_DSN//@postgres:/@127.0.0.1:}"
  export CATALOG_DSN="${CATALOG_DSN//@postgres/127.0.0.1}"
else
  echo "FAIL: set CATALOG_DSN in ingest/.env or CATALOG_DSN_HOST for host migrate" >&2
  exit 1
fi

cd "$INGEST_DIR"
echo "==> migrate catalog ($CATALOG_DSN)"
"$PY" -m app.migrate "$@"
