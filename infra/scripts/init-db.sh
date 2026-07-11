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
ON_DISK_PAYLOAD="${QDRANT_ON_DISK_PAYLOAD:-true}"
INT8_QUANT="${QDRANT_INT8_QUANTIZATION:-false}"

echo "Qdrant: ${QDRANT_URL} collection=${COLLECTION} dim=${DIM} on_disk_payload=${ON_DISK_PAYLOAD} int8=${INT8_QUANT}"

_build_create_json() {
  python3 - "$DIM" "$SPARSE" "$ON_DISK_PAYLOAD" "$INT8_QUANT" <<'PY'
import json
import sys

dim, sparse, on_disk_raw, int8_raw = sys.argv[1:5]
on_disk = on_disk_raw.lower() in ("true", "1", "yes")
int8 = int8_raw.lower() in ("true", "1", "yes")
body: dict = {
    "vectors": {"default": {"size": int(dim), "distance": "Cosine"}},
    "sparse_vectors": {sparse: {}},
    "on_disk_payload": on_disk,
}
if int8:
    body["quantization_config"] = {
        "scalar": {"type": "int8", "quantile": 0.99, "always_ram": True}
    }
print(json.dumps(body))
PY
}

_build_patch_json() {
  python3 - "$ON_DISK_PAYLOAD" "$INT8_QUANT" <<'PY'
import json
import sys

on_disk_raw, int8_raw = sys.argv[1:3]
on_disk = on_disk_raw.lower() in ("true", "1", "yes")
int8 = int8_raw.lower() in ("true", "1", "yes")
body: dict = {"on_disk_payload": on_disk}
if int8:
    body["quantization_config"] = {
        "scalar": {"type": "int8", "quantile": 0.99, "always_ram": True}
    }
print(json.dumps(body))
PY
}

if curl -sf "${QDRANT_URL}/collections/${COLLECTION}" >/dev/null 2>&1; then
  echo "collection exists: ${COLLECTION}"
  PATCH_JSON="$(_build_patch_json)"
  curl -sf -X PATCH "${QDRANT_URL}/collections/${COLLECTION}" \
    -H "Content-Type: application/json" \
    -d "${PATCH_JSON}"
  echo "applied Qdrant tuning (on_disk_payload=${ON_DISK_PAYLOAD}, int8=${INT8_QUANT})"
else
  CREATE_JSON="$(_build_create_json)"
  curl -sf -X PUT "${QDRANT_URL}/collections/${COLLECTION}" \
    -H "Content-Type: application/json" \
    -d "${CREATE_JSON}"
  echo "created collection: ${COLLECTION}"
fi

NEO4J_URI="${NEO4J_URI:-bolt://127.0.0.1:${NEO4J_BOLT_PORT:-7687}}"
echo "Neo4j: ${NEO4J_URI} (constraints applied by hybrid-rag-ingest migrations)"

echo ""
"${ROOT}/scripts/init-minio.sh"
