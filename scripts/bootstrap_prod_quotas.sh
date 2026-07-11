#!/usr/bin/env bash
# Seed default tenant quotas on ingest orchestrator (release checklist §4).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INGEST_URL="${INGEST_BASE_URL:-http://127.0.0.1:${ORCHESTRATOR_PORT:-8020}}"
TENANT="${BOOTSTRAP_TENANT_ID:-acme-corp}"

echo "==> seed quotas for $TENANT ($INGEST_URL)"
curl -sf "${INGEST_URL%/}/admin/healthz" >/dev/null || {
  echo "FAIL: ingest not healthy at $INGEST_URL" >&2
  exit 1
}

BODY='{
  "max_chunks": 500000,
  "max_collections": 50,
  "max_queries_per_minute": 120,
  "max_concurrent_streams": 50
}'

curl -sf -X PUT \
  "${INGEST_URL%/}/admin/tenants/${TENANT}/quotas" \
  -H "Content-Type: application/json" \
  -d "$BODY" >/dev/null

echo "OK: quotas configured for $TENANT"
