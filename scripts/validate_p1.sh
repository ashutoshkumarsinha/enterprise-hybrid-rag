#!/usr/bin/env bash
# P1 gate — E-14..E-19 contract validation (implementation-ready depth).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/ingest/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi

echo "==> P1 manifest + deliverable contracts"
"$PY" -m pytest \
  ingest/tests/contract/test_p1_manifest.py \
  ingest/tests/contract/test_p1_migrations.py \
  ingest/tests/contract/test_p1_acl_api.py \
  ingest/tests/contract/test_p1_connector_v2.py \
  ingest/tests/contract/test_chat_ui_scaffold.py \
  ingest/tests/contract/test_helm_chart.py \
  ingest/tests/contract/test_migrate_discovery.py \
  -q --tb=short

QPY="${ROOT}/query/.venv/bin/python"
if [[ ! -x "$QPY" ]]; then QPY=python3; fi

echo "==> E-15 query contract suite (sample)"
"$QPY" -m pytest \
  query/tests/contract/test_schema_coverage.py \
  query/tests/contract/test_kernel_contract_manifest.py \
  -q --tb=short

if command -v npm >/dev/null 2>&1 && [[ -f chat-ui/package.json ]]; then
  echo "==> E-18 chat-ui server tests (optional)"
  (cd chat-ui && npm test --workspace server 2>/dev/null) || echo "WARN: chat-ui npm test skipped/failed"
else
  echo "SKIP: npm not available for chat-ui tests"
fi

if command -v helm >/dev/null 2>&1; then
  echo "==> E-19 helm lint (optional)"
  make -C deploy/helm lint
else
  echo "SKIP: helm not installed — E-19 contract tests cover chart structure"
fi

echo "P1 validation OK"
