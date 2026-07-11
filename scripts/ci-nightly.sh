#!/usr/bin/env bash
# Nightly CI — PR suite + integration (when stack up) + benchmark + baseline compare.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/ci-pr.sh

echo "==> integration (query)"
(
  cd query
  chmod +x scripts/run-integration.sh 2>/dev/null || true
  LIVE_STACK="${LIVE_STACK:-1}" LIVE_STACK_STRICT="${LIVE_STACK_STRICT:-0}" \
    ./scripts/run-integration.sh -q || {
      if [[ "${LIVE_STACK_STRICT:-0}" == "1" ]]; then exit 1; fi
      echo "WARN: query integration skipped or failed (LIVE_STACK_STRICT=0)"
    }
)

echo "==> integration (ingest)"
(
  cd ingest
  chmod +x scripts/run-integration.sh 2>/dev/null || true
  LIVE_STACK="${LIVE_STACK:-1}" LIVE_STACK_STRICT="${LIVE_STACK_STRICT:-0}" \
    ./scripts/run-integration.sh -q || {
      if [[ "${LIVE_STACK_STRICT:-0}" == "1" ]]; then exit 1; fi
      echo "WARN: ingest integration skipped or failed (LIVE_STACK_STRICT=0)"
    }
)

echo "==> benchmark_rag (golden set + optional Ragas)"
(
  cd query
  PY=python3
  if [[ -x "${ROOT}/query/.venv/bin/python" ]]; then PY="${ROOT}/query/.venv/bin/python"; fi
  GOLDEN=benchmarks/golden_set.json
  if [[ ! -f "$GOLDEN" ]]; then GOLDEN=benchmarks/golden_set.json.example; fi
  "$PY" benchmarks/benchmark_rag.py \
    --limit 10 \
    --golden-set "$GOLDEN" \
    --output benchmarks/last_run.json \
    --ragas \
    --ragas-output benchmarks/last_ragas.json \
    --warn-total-p95-ms 45000 \
    --warn-faithfulness 0.80
)

echo "==> compare_benchmark_run"
(
  cd query
  PY=python3
  if [[ -x "${ROOT}/query/.venv/bin/python" ]]; then PY="${ROOT}/query/.venv/bin/python"; fi
  if [[ -f benchmarks/baselines.json ]]; then
    "$PY" benchmarks/compare_benchmark_run.py benchmarks/last_run.json benchmarks/baselines.json
  else
    echo "SKIP: benchmarks/baselines.json not committed — compare on release profile only"
  fi
)

echo "Nightly pipeline OK"
