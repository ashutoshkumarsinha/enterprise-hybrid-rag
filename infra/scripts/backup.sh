#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
[[ -f "$ENV_FILE" ]] && set -a && source "$ENV_FILE" && set +a
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${ROOT}/backups/${STAMP}"
mkdir -p "$BACKUP_DIR"

QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:${QDRANT_PORT:-6333}}"
COLLECTION="${QDRANT_COLLECTION:-enterprise_hybrid_rag}"

echo "Backing up Qdrant snapshot..."
curl -sf -X POST "${QDRANT_URL}/collections/${COLLECTION}/snapshots" \
  -o "${BACKUP_DIR}/qdrant-snapshot.json" || echo "qdrant snapshot: skipped"

echo "Backing up Postgres..."
docker compose -f "${ROOT}/compose/docker-compose.yml" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-postgres}" "${CATALOG_DB:-catalog}" \
  > "${BACKUP_DIR}/catalog.sql" || echo "postgres dump: skipped"

MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-change-me-in-production}"
BUCKET="${MINIO_BUCKET:-hybrid-rag}"
BUCKET_STAGING="${MINIO_BUCKET_STAGING:-hybrid-rag-staging}"
MC_IMAGE="${MINIO_MC_IMAGE:-minio/mc:RELEASE.2024-12-18T13-15-44Z}"
NETWORK="${DOCKER_NETWORK:-hybrid-rag-net}"

if docker network inspect "$NETWORK" >/dev/null 2>&1; then
  echo "Backing up MinIO buckets..."
  mc_mirror() {
    local bucket="$1" dest="$2"
    docker run --rm --network "$NETWORK" \
      -e "MC_HOST_minio=http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000" \
      -v "${dest}:/backup" \
      "$MC_IMAGE" mirror --overwrite "minio/${bucket}" "/backup" \
      || echo "minio mirror ${bucket}: skipped"
  }
  mkdir -p "${BACKUP_DIR}/minio-${BUCKET}" "${BACKUP_DIR}/minio-${BUCKET_STAGING}"
  mc_mirror "$BUCKET" "${BACKUP_DIR}/minio-${BUCKET}"
  mc_mirror "$BUCKET_STAGING" "${BACKUP_DIR}/minio-${BUCKET_STAGING}"
else
  echo "MinIO backup: skipped (network ${NETWORK} not found — run from infra with stack up)"
fi

echo "Backup written to ${BACKUP_DIR}"
