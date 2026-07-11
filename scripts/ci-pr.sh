#!/usr/bin/env bash
# PR CI — unit + contract for query and ingest (no GPU, no live stack).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> query unit + contract"
(
  cd query
  PY="${ROOT}/query/.venv/bin/python"
  if [[ ! -x "$PY" ]]; then PY=python3; fi
  "$PY" -m pytest tests/unit tests/contract -q --tb=short
)

echo "==> ingest unit + contract"
(
  cd ingest
  PY="${ROOT}/ingest/.venv/bin/python"
  if [[ ! -x "$PY" ]]; then PY=python3; fi
  "$PY" -m pytest tests/unit tests/contract -q --tb=short
)

echo "==> P1 gate (E-14..E-19)"
chmod +x scripts/validate_p1.sh 2>/dev/null || true
./scripts/validate_p1.sh

echo "PR unit+contract OK"
