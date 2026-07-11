#!/usr/bin/env bash
# P2 gate — E-34, E-24, E-25 + full P2 manifest contracts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/ingest/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi

echo "==> P2 manifest + E-34/E-24/E-25 contracts"
"$PY" -m pytest \
  ingest/tests/contract/test_p2_manifest.py \
  ingest/tests/contract/test_p2_mtls.py \
  ingest/tests/contract/test_cert_manager.py \
  ingest/tests/contract/test_p2_multi_region.py \
  ingest/tests/contract/test_p2_embed_migration.py \
  ingest/tests/contract/test_infra_caddyfile.py \
  -q --tb=short

echo "==> E-25 embed dimension dry-run"
"$PY" scripts/migrate_embed_dimension.py --dry-run

QPY="${ROOT}/query/.venv/bin/python"
if [[ ! -x "$QPY" ]]; then QPY=python3; fi

echo "==> P2 sample contracts (E-28, E-29, E-44)"
(
  cd query
  "$QPY" -m pytest \
    tests/unit/test_circuit_breaker.py \
    tests/unit/test_load_test.py \
    tests/unit/test_session_prune.py \
    -q --tb=short
)

echo "==> P2 ingest contracts (E-21, E-26)"
"$PY" -m pytest \
  ingest/tests/contract/test_tenant_purge.py \
  ingest/tests/contract/test_chaos_suite.py \
  ingest/tests/unit/test_quota_store.py \
  -q --tb=short

echo "P2 validation OK"
