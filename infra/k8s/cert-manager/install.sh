#!/usr/bin/env bash
# Install cert-manager into the cluster (platform prerequisite for production PKI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
NS="${CERT_MANAGER_NS:-cert-manager}"
VERSION="${CERT_MANAGER_VERSION:-v1.16.2}"
CHART_VERSION="${CERT_MANAGER_CHART_VERSION:-v1.16.2}"

if ! command -v helm >/dev/null 2>&1; then
  echo "FAIL: helm required" >&2
  exit 1
fi
if ! command -v kubectl >/dev/null 2>&1; then
  echo "FAIL: kubectl required" >&2
  exit 1
fi

helm repo add jetstack https://charts.jetstack.io >/dev/null 2>&1 || true
helm repo update jetstack >/dev/null

echo "==> cert-manager $VERSION (namespace $NS)"
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace "$NS" \
  --create-namespace \
  --version "$CHART_VERSION" \
  --set crds.enabled=true \
  --set prometheus.enabled=false \
  --wait --timeout 5m

echo "==> wait for cert-manager deployments"
kubectl rollout status deployment/cert-manager -n "$NS" --timeout=120s
kubectl rollout status deployment/cert-manager-webhook -n "$NS" --timeout=120s
kubectl rollout status deployment/cert-manager-cainjector -n "$NS" --timeout=120s

echo "OK: cert-manager installed"
