#!/usr/bin/env bash
set -euo pipefail
PORT="${QUERY_PORT:-8010}"
curl -sf "http://127.0.0.1:${PORT}/healthz" | grep -q '"research_ready": true'
echo "query: ok"
