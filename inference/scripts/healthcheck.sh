#!/usr/bin/env bash
set -euo pipefail
check() {
  local name="$1" url="$2"
  if curl -sf "$url" >/dev/null 2>&1; then
    echo "${name}: ok"
  else
    echo "${name}: down"
    return 1
  fi
}
fail=0
check chat-llm "http://127.0.0.1:${CHAT_LLM_PORT:-8000}/v1/models" || fail=1
check embedding "http://127.0.0.1:${EMBED_PORT:-8001}/v1/models" || fail=1
check vision "http://127.0.0.1:${VISION_PORT:-8002}/v1/models" || true
check reranker "http://127.0.0.1:${RERANKER_PORT:-8091}/healthz" || fail=1
check reranker-fast "http://127.0.0.1:${RERANKER_FAST_PORT:-8092}/healthz" || true
check smoke-llm "http://127.0.0.1:${SMOKE_LLM_PORT:-8011}/v1/models" || true
exit $fail
