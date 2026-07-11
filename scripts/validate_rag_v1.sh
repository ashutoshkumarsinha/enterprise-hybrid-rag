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
"$PY" -m pytest \
  ingest/tests/contract/test_rag_v1_gate.py \
  ingest/tests/contract/test_federated_research.py \
  ingest/tests/contract/test_langfuse_bootstrap.py \
  -q --tb=short

echo "==> Full unit + contract (query + ingest)"
(
  cd query
  "$QPY" -m pytest tests/unit tests/contract -q --tb=line
)
(
  cd ingest
  "$PY" -m pytest tests/unit tests/contract -q --tb=line
)

if [[ "${PRE_RELEASE:-0}" == "1" ]]; then
  echo "==> Pre-release live stack (PRE_RELEASE=1)"
  chmod +x scripts/validate_live_stack.sh 2>/dev/null || true
  ./scripts/validate_live_stack.sh
elif [[ "${LIVE_STACK:-0}" == "1" ]]; then
  echo "==> Live integration (LIVE_STACK=1)"
  (
    cd query
    "$QPY" -m pytest tests/integration -q --tb=short
  )
else
  echo "SKIP: live integration — set LIVE_STACK=1 or PRE_RELEASE=1 for pre-release"
fi

if [[ "${RAGAS_GATE:-0}" == "1" ]]; then
  echo "==> Ragas golden set"
  RAGAS_CMD=(
    benchmarks/benchmark_rag.py --ragas --limit "${RAGAS_LIMIT:-4}"
    --golden-set benchmarks/golden_set.json.example
    --warn-faithfulness 0.85 --warn-total-p95-ms 45000
  )
  if [[ "${PRE_RELEASE:-0}" == "1" || "${RAGAS_GATE_STRICT:-0}" == "1" ]]; then
    RAGAS_CMD+=(--live-stack --fail-faithfulness 0.85 --fail-total-p95-ms 60000)
  fi
  (cd query && "$QPY" "${RAGAS_CMD[@]}") || {
    [[ "${PRE_RELEASE:-0}" == "1" ]] && exit 1
    echo "WARN: Ragas gate failed/skipped"
  }
  if [[ -f query/benchmarks/baselines.json ]]; then
    (cd query && "$QPY" benchmarks/compare_benchmark_run.py --fail-ratio 1.1) || {
      [[ "${PRE_RELEASE:-0}" == "1" ]] && exit 1
      echo "WARN: baseline compare failed"
    }
  fi
else
  echo "SKIP: Ragas — set RAGAS_GATE=1 for pre-release"
fi

if [[ "${LOAD_GATE:-0}" == "1" ]]; then
  echo "==> Load soak"
  LOAD_CMD=(benchmarks/load_test.py --backend "${LOAD_BACKEND:-http}")
  if [[ "${LOAD_BACKEND:-http}" == "http" ]]; then
    LOAD_CMD+=(--requests "${LOAD_REQUESTS:-20}" --fail-p95-s "${LOAD_FAIL_P95_S:-120}")
  else
    LOAD_CMD+=(--duration "${LOAD_DURATION:-30s}" --concurrency "${LOAD_CONCURRENCY:-50}" --fail-p95-s 20)
  fi
  (cd query && "$QPY" "${LOAD_CMD[@]}") || {
    [[ "${PRE_RELEASE:-0}" == "1" ]] && exit 1
    echo "WARN: load_test failed/skipped"
  }
else
  echo "SKIP: k6/Locust — set LOAD_GATE=1 for pre-release"
fi

echo ""
if [[ "${PRE_RELEASE:-0}" == "1" ]]; then
  echo "rag-v1.0 pre-release validation OK"
else
  echo "rag-v1.0 validation OK (CI gate)"
  echo "Pre-release: make bootstrap && make validate-pre-release"
  echo "Or: PRE_RELEASE=1 RAGAS_GATE=1 LOAD_GATE=1 make validate-rag-v1"
fi
