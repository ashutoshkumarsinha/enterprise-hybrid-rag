#!/usr/bin/env bash
# PR CI — rag-v1.0 gate (P1+P2+P3 + config alignment + unit/contract).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

chmod +x scripts/validate_rag_v1.sh scripts/validate_config_alignment.py 2>/dev/null || true
./scripts/validate_rag_v1.sh

echo "PR CI OK"
