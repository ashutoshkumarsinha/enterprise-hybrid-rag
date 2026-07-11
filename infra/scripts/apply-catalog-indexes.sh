#!/usr/bin/env bash
# Apply INF-P2 supplemental catalog indexes (idempotent).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
INGEST_ENV="${ROOT}/../ingest/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a && source "$ENV_FILE" && set +a
elif [[ -f "$INGEST_ENV" ]]; then
  set -a && source "$INGEST_ENV" && set +a
fi

DSN="${CATALOG_DSN:-}"
if [[ -z "$DSN" ]]; then
  echo "WARN: CATALOG_DSN unset — skipping catalog indexes"
  exit 0
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "WARN: psql not found — skipping catalog indexes"
  exit 0
fi

psql "$DSN" -v ON_ERROR_STOP=1 -f "${ROOT}/scripts/postgres-catalog-indexes.sql"
echo "catalog indexes applied"
