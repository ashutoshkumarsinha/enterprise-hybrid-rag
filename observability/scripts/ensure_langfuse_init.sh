#!/usr/bin/env bash
# Ensure observability/.env has Langfuse headless-init variables (IF-5).
set -euo pipefail
OBS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${OBS_ENV_FILE:-$OBS_DIR/.env}"
EXAMPLE="$OBS_DIR/.env.example"
ENV_SET="$OBS_DIR/../scripts/env_set.py"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from .env.example"
fi

gen_hex() { openssl rand -hex 16; }
gen_hex32() { openssl rand -hex 32; }

get_var() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || true
}

is_empty() {
  local val="$1"
  [[ -z "$val" || "$val" == "generate-with-openssl-rand-hex-32" || "$val" == *change-me* ]]
}

set_var() {
  python3 "$ENV_SET" "$ENV_FILE" "$1" "$2"
}

ensure() {
  local key="$1" val="$2"
  local current
  current="$(get_var "$key")"
  if is_empty "$current"; then
    set_var "$key" "$val"
  fi
}

ensure LANGFUSE_NEXTAUTH_SECRET "$(gen_hex32)"
ensure LANGFUSE_SALT "$(gen_hex32)"
ensure LANGFUSE_ENCRYPTION_KEY "$(gen_hex32)"
ensure LANGFUSE_INIT_ORG_ID "hybrid-rag"
ensure LANGFUSE_INIT_ORG_NAME "Enterprise Hybrid RAG"
ensure LANGFUSE_INIT_PROJECT_ID "hybrid-rag-query"
ensure LANGFUSE_INIT_PROJECT_NAME "hybrid-rag-query"
ensure LANGFUSE_INIT_PROJECT_PUBLIC_KEY "pk-lf-$(gen_hex)"
ensure LANGFUSE_INIT_PROJECT_SECRET_KEY "sk-lf-$(gen_hex)"
ensure LANGFUSE_INIT_USER_EMAIL "admin@hybrid-rag.local"
ensure LANGFUSE_INIT_USER_PASSWORD "langfuse-$(gen_hex)"
ensure LANGFUSE_INIT_USER_NAME "Hybrid RAG Admin"

echo "OK: Langfuse init env ready in $ENV_FILE"
echo "    LANGFUSE_INIT_PROJECT_PUBLIC_KEY=$(get_var LANGFUSE_INIT_PROJECT_PUBLIC_KEY)"
