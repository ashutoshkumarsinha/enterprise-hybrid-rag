#!/usr/bin/env bash
set -euo pipefail

fail=0
check() {
  local name="$1" cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "${name}: ok"
  else
    echo "${name}: down"
    fail=1
  fi
}

check collector-health "curl -sf http://127.0.0.1:13133/"
check collector-metrics "curl -sf http://127.0.0.1:8889/metrics"
check jaeger-ui "curl -sf http://127.0.0.1:${JAEGER_UI_PORT:-16686}"
check langfuse "curl -sf http://127.0.0.1:${LANGFUSE_PORT:-3000}/api/public/health"

exit $fail
