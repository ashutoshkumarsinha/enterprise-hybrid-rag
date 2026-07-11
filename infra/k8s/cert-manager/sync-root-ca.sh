#!/usr/bin/env bash
# Copy hybrid-rag root CA secret into the application namespace for query mTLS client-CA mount.
set -euo pipefail
SRC_NS="${CERT_MANAGER_NS:-cert-manager}"
SRC_SECRET="${CA_SECRET_NAME:-hybrid-rag-root-ca}"
DST_NS="${1:-hybrid-rag}"
DST_SECRET="${CA_SECRET_NAME:-hybrid-rag-root-ca}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "FAIL: kubectl required" >&2
  exit 1
fi

kubectl get secret "$SRC_SECRET" -n "$SRC_NS" >/dev/null

kubectl get secret "$SRC_SECRET" -n "$SRC_NS" -o json | python3 -c "
import json, sys
doc = json.load(sys.stdin)
meta = doc.setdefault('metadata', {})
meta['namespace'] = sys.argv[1]
meta.pop('resourceVersion', None)
meta.pop('uid', None)
meta.pop('creationTimestamp', None)
meta.pop('managedFields', None)
json.dump(doc, sys.stdout)
" "$DST_NS" | kubectl apply -f -

echo "OK: copied $SRC_SECRET from $SRC_NS → $DST_NS"
