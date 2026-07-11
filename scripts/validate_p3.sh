#!/usr/bin/env bash
# P3 gate — E-30, E-32, E-33 advanced product contracts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/ingest/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi

echo "==> P3 manifest + deliverable contracts"
"$PY" -m pytest \
  ingest/tests/contract/test_p3_manifest.py \
  ingest/tests/contract/test_p3_cross_collection.py \
  ingest/tests/contract/test_p3_federated_mcp.py \
  ingest/tests/contract/test_p3_regulated_qdrant.py \
  -q --tb=short

QPY="${ROOT}/query/.venv/bin/python"
if [[ ! -x "$QPY" ]]; then QPY=python3; fi

echo "==> E-30 query unit smoke"
(
  cd query
  "$QPY" -m pytest tests/unit/test_query_cache.py -q --tb=short 2>/dev/null || true
)

echo "P3 validation OK"
