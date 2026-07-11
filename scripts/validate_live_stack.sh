#!/usr/bin/env bash
# Pre-release live-stack gate — health, migrate, Keycloak, integration, optional Ragas/load.
# Usage:
#   make validate-pre-release          # after make bootstrap
#   PRE_RELEASE=1 make validate-rag-v1   # CI gate + live stack
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

QPY="${ROOT}/query/.venv/bin/python"
IPY="${ROOT}/ingest/.venv/bin/python"
if [[ ! -x "$QPY" ]]; then QPY=python3; fi
if [[ ! -x "$IPY" ]]; then IPY=python3; fi

STRICT="${PRE_RELEASE_STRICT:-1}"
fail() { echo "FAIL: $*" >&2; exit 1; }
warn() { echo "WARN: $*" >&2; }

echo "==> All-plane health (IF-1, IF-4, IF-5, infra SLOs)"
make health

echo "==> Catalog init-db idempotency"
make infra-init-db

echo "==> Catalog migrations (001–005)"
chmod +x scripts/migrate_catalog.sh
./scripts/migrate_catalog.sh
cd "$ROOT/ingest"
if [[ -f "$ROOT/ingest/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/ingest/.env"
  set +a
fi
export CATALOG_DSN="${CATALOG_DSN_HOST:-${CATALOG_DSN//@postgres:/@127.0.0.1:}}"
PENDING_COUNT="$("$IPY" -m app.migrate --status | "$IPY" -c 'import json,sys; print(len(json.load(sys.stdin).get("pending",[])))')"
if [[ "$PENDING_COUNT" != "0" ]]; then
  fail "pending catalog migrations: $PENDING_COUNT"
fi
cd "$ROOT"

echo "==> Keycloak realm ready (IF-6)"
curl -sf "http://127.0.0.1:${KEYCLOAK_PORT:-8081}/health/ready" | grep -q UP || fail "Keycloak not ready"

echo "==> Langfuse API keys (IF-5)"
chmod +x scripts/bootstrap_langfuse_keys.sh observability/scripts/ensure_langfuse_init.sh
./observability/scripts/ensure_langfuse_init.sh
./scripts/bootstrap_langfuse_keys.sh
if [[ -f query/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source query/.env
  set +a
fi
[[ -n "${LANGFUSE_PUBLIC_KEY:-}" && -n "${LANGFUSE_SECRET_KEY:-}" ]] || fail "LANGFUSE_* keys missing in query/.env"
curl -sf "http://127.0.0.1:${LANGFUSE_PORT:-3000}/api/public/health" >/dev/null || warn "Langfuse health endpoint unreachable"

echo "==> MCP bootstrap token"
chmod +x scripts/bootstrap_mcp_token.sh scripts/bootstrap_prod_quotas.sh
./scripts/bootstrap_mcp_token.sh
./scripts/bootstrap_prod_quotas.sh

echo "==> Live integration tests"
export LIVE_STACK=1
(
  cd query
  "$QPY" -m pytest tests/integration -q --tb=short
)

echo "==> Ragas golden set (RAGAS_GATE)"
RAGAS_ARGS=(
  benchmarks/benchmark_rag.py
  --live-stack
  --limit "${RAGAS_LIMIT:-4}"
  --golden-set benchmarks/golden_set.json.example
  --ragas
  --warn-faithfulness 0.85
  --warn-total-p95-ms 45000
)
if [[ "${RAGAS_GATE_STRICT:-0}" == "1" ]]; then
  RAGAS_ARGS+=(--fail-faithfulness 0.85 --fail-total-p95-ms 60000)
fi
if (cd query && "$QPY" "${RAGAS_ARGS[@]}"); then
  if [[ -f query/benchmarks/baselines.json ]]; then
    (cd query && "$QPY" benchmarks/compare_benchmark_run.py --fail-ratio 1.1) || {
      [[ "$STRICT" == "1" ]] && fail "baseline regression"
      warn "baseline regression (non-strict)"
    }
  else
    warn "query/benchmarks/baselines.json missing — skip compare"
  fi
else
  [[ "$STRICT" == "1" ]] && fail "Ragas benchmark"
  warn "Ragas benchmark skipped or failed (install query/benchmarks/requirements.txt)"
fi

echo "==> Load soak (LOAD_GATE)"
LOAD_BACKEND="${LOAD_BACKEND:-http}"
LOAD_ARGS=(
  benchmarks/load_test.py
  --backend "$LOAD_BACKEND"
  --url "${QUERY_BASE_URL:-http://127.0.0.1:8010}"
  --concurrency "${LOAD_CONCURRENCY:-20}"
)
if [[ "$LOAD_BACKEND" == "http" ]]; then
  LOAD_ARGS+=(--requests "${LOAD_REQUESTS:-20}" --fail-p95-s "${LOAD_FAIL_P95_S:-120}")
else
  LOAD_ARGS+=(--duration "${LOAD_DURATION:-30s}" --fail-p95-s "${LOAD_FAIL_P95_S:-20}")
  if [[ "${LOAD_GATE_FULL:-0}" == "1" ]]; then
    LOAD_ARGS=(benchmarks/load_test.py --backend k6 --duration 30m --concurrency 50 --fail-p95-s 20)
  fi
fi
(cd query && "$QPY" "${LOAD_ARGS[@]}") || {
  [[ "$STRICT" == "1" ]] && fail "load_test"
  warn "load_test failed"
}

if [[ "${MCP_MTLS_SMOKE:-0}" == "1" ]]; then
  echo "==> mTLS smoke"
  CERT_DIR="${MTLS_CERT_DIR:-$ROOT/infra/certs/dev}"
  if [[ -f "$CERT_DIR/client.crt" && -f "$CERT_DIR/client.key" ]]; then
    curl -sf --cert "$CERT_DIR/client.crt" --key "$CERT_DIR/client.key" \
      --cacert "$CERT_DIR/ca.crt" \
      "https://127.0.0.1:${QUERY_TLS_PORT:-8443}/healthz" >/dev/null \
      || fail "mTLS healthz smoke"
    echo "OK: mTLS healthz"
  else
    warn "mTLS certs missing — run: make -C infra mtls-dev-certs"
  fi
fi

echo ""
echo "pre-release live-stack validation OK"
