#!/usr/bin/env bash
# Verify cert-manager controllers and CRDs are healthy.
set -euo pipefail
NS="${CERT_MANAGER_NS:-cert-manager}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "FAIL: kubectl required" >&2
  exit 1
fi

kubectl get crd certificates.cert-manager.io issuers.cert-manager.io clusterissuers.cert-manager.io >/dev/null

for dep in cert-manager cert-manager-webhook cert-manager-cainjector; do
  kubectl rollout status "deployment/$dep" -n "$NS" --timeout=60s
done

READY="$(kubectl get pods -n "$NS" -l app.kubernetes.io/instance=cert-manager \
  -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
if echo "$READY" | grep -q False; then
  echo "FAIL: cert-manager pods not ready" >&2
  kubectl get pods -n "$NS"
  exit 1
fi

echo "OK: cert-manager healthy (namespace $NS)"
