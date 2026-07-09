#!/usr/bin/env bash
set -euo pipefail
BASE="http://127.0.0.1:8011/v1"
MODEL="${SMOKE_LLM_MODEL:-meta-llama/Llama-3.2-1B-Instruct}"
curl -sf "${BASE}/models" >/dev/null
curl -sf "${BASE}/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}],\"max_tokens\":4}" \
  | grep -q "choices"
echo "smoke-llm: ok"
