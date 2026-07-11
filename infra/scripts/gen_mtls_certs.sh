#!/usr/bin/env bash
# Generate dev mTLS CA + server (query) + client (Caddy) certificates.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${MTLS_CERT_DIR:-$ROOT/infra/certs/dev}"
DAYS="${MTLS_CERT_DAYS:-825}"
CN="${MTLS_SERVER_CN:-hybrid-rag-query}"

mkdir -p "$OUT"
chmod 700 "$OUT"

gen_if_missing() {
  local name="$1"
  shift
  if [[ ! -f "$OUT/$name" ]]; then
    "$@"
  fi
}

echo "==> mTLS dev certs → $OUT"

# CA
if [[ ! -f "$OUT/ca.key" ]]; then
  openssl genrsa -out "$OUT/ca.key" 4096
  openssl req -x509 -new -nodes -key "$OUT/ca.key" -sha256 -days "$DAYS" \
    -out "$OUT/ca.crt" -subj "/CN=Hybrid RAG Dev CA"
fi

# Query server cert
if [[ ! -f "$OUT/server.key" ]]; then
  openssl genrsa -out "$OUT/server.key" 2048
  openssl req -new -key "$OUT/server.key" -out "$OUT/server.csr" \
    -subj "/CN=$CN"
  openssl x509 -req -in "$OUT/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
    -CAcreateserial -out "$OUT/server.crt" -days "$DAYS" -sha256 \
    -extfile <(printf "subjectAltName=DNS:localhost,DNS:query,IP:127.0.0.1")
fi

# Caddy client cert (upstream to query)
if [[ ! -f "$OUT/caddy-client.key" ]]; then
  openssl genrsa -out "$OUT/caddy-client.key" 2048
  openssl req -new -key "$OUT/caddy-client.key" -out "$OUT/caddy-client.csr" \
    -subj "/CN=caddy-upstream"
  openssl x509 -req -in "$OUT/caddy-client.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
    -CAcreateserial -out "$OUT/caddy-client.crt" -days "$DAYS" -sha256
fi

# Symlinks expected by tls_config / Caddy examples
ln -sf ca.crt "$OUT/client-ca.crt"
ln -sf caddy-client.crt "$OUT/client.crt"
ln -sf caddy-client.key "$OUT/client.key"

chmod 600 "$OUT"/*.key 2>/dev/null || true
echo "OK: ca.crt server.{crt,key} caddy-client.{crt,key} client-ca.crt"
