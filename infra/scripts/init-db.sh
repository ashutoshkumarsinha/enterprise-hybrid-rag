#!/usr/bin/env bash
# Initialize Qdrant collection and verify Neo4j connectivity.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
[[ -f "$ENV_FILE" ]] && set -a && source "$ENV_FILE" && set +a

QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:${QDRANT_PORT:-6333}}"
COLLECTION="${QDRANT_COLLECTION:-enterprise_hybrid_rag}"
DIM="${EMBED_DIMENSION:-768}"
SPARSE="${SPARSE_VECTOR_NAME:-bm25-text}"

echo "Qdrant: ${QDRANT_URL} collection=${COLLECTION} dim=${DIM}"

if curl -sf "${QDRANT_URL}/collections/${COLLECTION}" >/dev/null 2>&1; then
  echo "collection exists: ${COLLECTION}"
else
  curl -sf -X PUT "${QDRANT_URL}/collections/${COLLECTION}" \
    -H "Content-Type: application/json" \
    -d "{
      \"vectors\": {
        \"default\": {
          \"size\": ${DIM},
          \"distance\": \"Cosine\"
        }
      },
      \"sparse_vectors\": {
        \"${SPARSE}\": {}
      }
    }"
  echo "created collection: ${COLLECTION}"
fi

NEO4J_URI="${NEO4J_URI:-bolt://127.0.0.1:${NEO4J_BOLT_PORT:-7687}}"
echo "Neo4j: ${NEO4J_URI} (constraints applied by hybrid-rag-ingest migrations)"

echo ""
"${ROOT}/scripts/init-minio.sh"
