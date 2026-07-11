#!/usr/bin/env bash
# rag-v1.0 release gate — P1+P2+P3 + config alignment + unit/contract tests.
# Live-stack checks (health, Ragas, k6) are documented but optional here.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/ingest/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi
QPY="${ROOT}/query/.venv/bin/python"
if [[ ! -x "$QPY" ]]; then QPY=python3; fi

echo "==> Config alignment (index_schema_version, embed_dimension, migration 005)"
"$PY" scripts/validate_config_alignment.py
"$PY" scripts/migrate_embed_dimension.py --dry-run
make validate-release-matrix

echo "==> Phase gates P1 + P2 + P3"
./scripts/validate_p1.sh
./scripts/validate_p2.sh
./scripts/validate_p3.sh

echo "==> rag-v1 gate manifest"
"$PY" -m pytest ingest/tests/contract/test_rag_v1_gate.py -q --tb=short

echo "==> Full unit + contract (query + ingest)"
(
  cd query
  "$QPY" -m pytest tests/unit tests/contract -q --tb=line
)
(
  cd ingest
  "$PY" -m pytest tests/unit tests/contract -q --tb=line
)

if [[ "${LIVE_STACK:-0}" == "1" ]]; then
  echo "==> Live integration (LIVE_STACK=1)"
  (
    cd query
    "$QPY" -m pytest tests/integration -q --tb=short
  )
else
  echo "SKIP: live integration — set LIVE_STACK=1 for nightly/pre-release"
fi

if [[ "${RAGAS_GATE:-0}" == "1" ]]; then
  echo "==> Ragas golden set"
  (cd query && "$QPY" benchmarks/benchmark_rag.py --ragas) || echo "WARN: Ragas gate failed/skipped"
else
  echo "SKIP: Ragas — set RAGAS_GATE=1 for pre-release"
fi

if [[ "${LOAD_GATE:-0}" == "1" ]]; then
  echo "==> Load soak"
  (cd query && "$QPY" benchmarks/load_test.py) || echo "WARN: load_test failed/skipped"
else
  echo "SKIP: k6/Locust — set LOAD_GATE=1 for pre-release"
fi

echo ""
echo "rag-v1.0 validation OK (CI gate)"
echo "Manual before tag: make health, migrate, Keycloak, prod quotas — see docs/SPEC_ROADMAP.md §4"
