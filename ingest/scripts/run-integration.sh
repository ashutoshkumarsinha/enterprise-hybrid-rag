#!/usr/bin/env bash
# Run live-stack ingest integration tests (§13.4).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export LIVE_STACK="${LIVE_STACK:-1}"
export LIVE_STACK_STRICT="${LIVE_STACK_STRICT:-0}"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY=python3
fi

echo "LIVE_STACK=$LIVE_STACK LIVE_STACK_STRICT=$LIVE_STACK_STRICT"
exec "$PY" -m pytest tests/integration "$@"
