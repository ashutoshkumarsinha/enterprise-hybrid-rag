#!/usr/bin/env bash
set -euo pipefail
PORT="${ORCHESTRATOR_PORT:-8020}"
curl -sf "http://127.0.0.1:${PORT}/admin/healthz" | grep -q '"status": "ok"'
echo "orchestrator: ok"
