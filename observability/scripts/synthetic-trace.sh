#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENDPOINT="${OTEL_EXPORTER_OTLP_ENDPOINT:-http://127.0.0.1:4317}"

if command -v python3 >/dev/null; then
  pip install -q opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc 2>/dev/null || true
  OTEL_EXPORTER_OTLP_ENDPOINT="$ENDPOINT" OTEL_SERVICE_NAME=hybrid-rag-synthetic \
    python3 "${ROOT}/scripts/synthetic_trace.py"
else
  echo "python3 required for synthetic trace"
  exit 1
fi

echo "View traces: http://localhost:${JAEGER_UI_PORT:-16686}"
