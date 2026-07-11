# Bootstrap internal PKI for hybrid-rag mTLS (dev/staging clusters).
#
# Flow:
#   1. make cert-manager-install
#   2. make cert-manager-issuer
#   3. helm install hybrid-rag ... (certManager.certificates.enabled=true)
#
# Production: replace ClusterIssuer names in values-prod.yaml with corporate PKI
# or Let's Encrypt for public ingress TLS.
