#!/usr/bin/env bash
# Build (or mirror-tag) Docker images for all hybrid-rag sub-projects via Packer.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-dev}"
REGISTRY="${REGISTRY:-}"
PUSH="${PUSH:-false}"
VAR_FILE="${PACKER_VAR_FILE:-}"

ARGS=(-var "image_tag=${IMAGE_TAG}" -var "registry=${REGISTRY}" -var "push=${PUSH}")
if [[ -n "$VAR_FILE" && -f "$VAR_FILE" ]]; then
  ARGS+=(-var-file="$VAR_FILE")
elif [[ -f "${ROOT}/packer/versions.pkrvars.hcl" ]]; then
  ARGS+=(-var-file="${ROOT}/packer/versions.pkrvars.hcl")
fi

PROJECTS=(query ingest inference infra observability)

for proj in "${PROJECTS[@]}"; do
  dir="${ROOT}/${proj}/packer"
  if [[ ! -f "${dir}/images.pkr.hcl" ]]; then
    echo "skip ${proj}: no packer/images.pkr.hcl"
    continue
  fi
  echo "=== packer: ${proj} (tag=${IMAGE_TAG}) ==="
  (cd "${ROOT}/${proj}" && packer init packer && packer build "${ARGS[@]}" packer/)
done

echo "Done. Images tagged with: ${IMAGE_TAG}"
if [[ -n "$REGISTRY" ]]; then
  echo "Registry prefix: ${REGISTRY}"
fi
