#!/usr/bin/env bash
# Chaos suite wrapper — monthly staging (E-26, spec §13.1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY=python3
if [[ -x "${ROOT}/query/.venv/bin/python" ]]; then
  PY="${ROOT}/query/.venv/bin/python"
fi

MODE_ARGS=(--dry-run)
if [[ "${CHAOS_APPLY:-0}" == "1" ]]; then
  MODE_ARGS=(--apply)
fi

exec "$PY" scripts/chaos/chaos_suite.py "${MODE_ARGS[@]}" "$@"
