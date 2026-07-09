#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
[[ -f "$ENV_FILE" ]] && set -a && source "$ENV_FILE" && set +a

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

check qdrant "curl -sf http://127.0.0.1:${QDRANT_PORT:-6333}/readyz"
check neo4j "curl -sf http://127.0.0.1:${NEO4J_HTTP_PORT:-7474}"
check redis "redis-cli -p ${REDIS_PORT:-6379} ping | grep -q PONG"
check minio "curl -sf http://127.0.0.1:${MINIO_API_PORT:-9000}/minio/health/live"
check postgres "pg_isready -h 127.0.0.1 -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-postgres}"
check keycloak "curl -sf http://127.0.0.1:${KEYCLOAK_PORT:-8081}/health/ready"

if docker compose -f "$(dirname "$0")/../compose/docker-compose.yml" --profile edge ps caddy 2>/dev/null | grep -q Up; then
  check caddy "curl -sf http://127.0.0.1:${CADDY_HTTP_PORT:-8080}"
fi

exit $fail
