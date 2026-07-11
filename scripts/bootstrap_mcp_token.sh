#!/usr/bin/env bash
# Mint bootstrap MCP admin token when query is up (IF-6).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUERY_DIR="$ROOT/query"
PY="${QUERY_DIR}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi

QUERY_URL="${QUERY_BASE_URL:-http://127.0.0.1:${QUERY_PORT:-8010}}"
TENANT="${BOOTSTRAP_TENANT_ID:-acme-corp}"
PRINCIPAL="${BOOTSTRAP_PRINCIPAL:-user:admin}"
TOKEN_FILE="${MCP_TOKEN_FILE:-$QUERY_DIR/.mcp-bootstrap-token}"

if [[ -f "$QUERY_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$QUERY_DIR/.env"
  set +a
fi

echo "==> wait query health ($QUERY_URL)"
for _ in $(seq 1 60); do
  if curl -sf "${QUERY_URL%/}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -sf "${QUERY_URL%/}/healthz" >/dev/null || {
  echo "FAIL: query not healthy at $QUERY_URL" >&2
  exit 1
}

if [[ -n "${MCP_ACCESS_TOKEN:-}" ]]; then
  echo "OK: MCP_ACCESS_TOKEN already set in environment"
  exit 0
fi

if [[ -f "$TOKEN_FILE" ]]; then
  echo "OK: bootstrap token file exists ($TOKEN_FILE)"
  exit 0
fi

export ALLOW_TOKEN_BOOTSTRAP=true
cd "$QUERY_DIR"
# Rewrite docker hostnames for CLI when running on host.
export CATALOG_DSN_TOKEN="${CATALOG_DSN_TOKEN//@postgres:/@127.0.0.1:}"
export CATALOG_DSN_SESSION="${CATALOG_DSN_SESSION//@postgres:/@127.0.0.1:}"
export CATALOG_DSN_RO="${CATALOG_DSN_RO//@postgres:/@127.0.0.1:}"

RESULT="$("$PY" -m app.cli mint-mcp-token \
  --tenant "$TENANT" \
  --principal "$PRINCIPAL" \
  --template admin \
  --label bootstrap)"

TOKEN="$(echo "$RESULT" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
printf '%s\n' "$TOKEN" >"$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"
echo "OK: wrote bootstrap MCP token to $TOKEN_FILE"
echo "    export MCP_ACCESS_TOKEN=\$(cat $TOKEN_FILE)"
