#!/usr/bin/env bash
# Create MinIO buckets and dev IAM users for hybrid-rag-infra.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
[[ -f "$ENV_FILE" ]] && set -a && source "$ENV_FILE" && set +a

MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-change-me-in-production}"
BUCKET="${MINIO_BUCKET:-hybrid-rag}"
BUCKET_STAGING="${MINIO_BUCKET_STAGING:-hybrid-rag-staging}"

INGEST_USER="${MINIO_INGEST_ACCESS_KEY:-hybrid-rag-ingest}"
INGEST_SECRET="${MINIO_INGEST_SECRET_KEY:-change-me-ingest-minio}"
QUERY_USER="${MINIO_QUERY_ACCESS_KEY:-hybrid-rag-query}"
QUERY_SECRET="${MINIO_QUERY_SECRET_KEY:-change-me-query-minio}"

MC_IMAGE="${MINIO_MC_IMAGE:-minio/mc:RELEASE.2024-12-18T13-15-44Z}"
NETWORK="${DOCKER_NETWORK:-hybrid-rag-net}"

mc() {
  docker run --rm --network "$NETWORK" \
    -e "MC_HOST_minio=http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000" \
    "$MC_IMAGE" "$@"
}

echo "MinIO: waiting for minio:9000 on network ${NETWORK}..."
for _ in $(seq 1 30); do
  if mc ready minio >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
mc ready minio

echo "MinIO: ensuring buckets ${BUCKET}, ${BUCKET_STAGING}..."
mc mb --ignore-existing "minio/${BUCKET}"
mc mb --ignore-existing "minio/${BUCKET_STAGING}"

# Dev service accounts — production should use external secrets + tighter policies.
if ! mc admin user info minio "${INGEST_USER}" >/dev/null 2>&1; then
  mc admin user add minio "${INGEST_USER}" "${INGEST_SECRET}"
fi
if ! mc admin user info minio "${QUERY_USER}" >/dev/null 2>&1; then
  mc admin user add minio "${QUERY_USER}" "${QUERY_SECRET}"
fi

POLICY_DIR="$(mktemp -d)"
trap 'rm -rf "$POLICY_DIR"' EXIT

cat >"${POLICY_DIR}/ingest-rw.json" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::${BUCKET}/*",
        "arn:aws:s3:::${BUCKET}",
        "arn:aws:s3:::${BUCKET_STAGING}/*",
        "arn:aws:s3:::${BUCKET_STAGING}"
      ]
    }
  ]
}
EOF

cat >"${POLICY_DIR}/query-ro.json" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::${BUCKET}/*",
        "arn:aws:s3:::${BUCKET_STAGING}/*"
      ]
    }
  ]
}
EOF

docker run --rm --network "$NETWORK" \
  -e "MC_HOST_minio=http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000" \
  -v "${POLICY_DIR}:/policies:ro" \
  "$MC_IMAGE" admin policy create minio hybrid-rag-ingest-rw /policies/ingest-rw.json 2>/dev/null || true
docker run --rm --network "$NETWORK" \
  -e "MC_HOST_minio=http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000" \
  -v "${POLICY_DIR}:/policies:ro" \
  "$MC_IMAGE" admin policy create minio hybrid-rag-query-ro /policies/query-ro.json 2>/dev/null || true

mc admin policy attach minio hybrid-rag-ingest-rw --user "${INGEST_USER}"
mc admin policy attach minio hybrid-rag-query-ro --user "${QUERY_USER}"

echo "MinIO init complete."
echo "  bucket (documents + images): ${BUCKET}"
echo "  bucket (staging / multipart):  ${BUCKET_STAGING}"
echo "  ingest credentials: ${INGEST_USER} (policy hybrid-rag-ingest-rw)"
echo "  query credentials:  ${QUERY_USER} (policy hybrid-rag-query-ro)"
echo "  console: http://127.0.0.1:${MINIO_CONSOLE_PORT:-9001}"
