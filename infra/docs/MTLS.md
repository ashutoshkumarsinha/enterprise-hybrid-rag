# mTLS Between Tiers (E-34)

**Owner:** `hybrid-rag-infra`  
**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md §18.15 (transport security)  
**Profile:** `edge` + `[caddy.mtls]` in `config/infra.toml`

Enterprise deployments SHOULD encrypt and mutually authenticate traffic between the **public edge** (Caddy) and **application tiers** (query, ingest), and optionally between query and data-plane services.

---

## 1. Threat model

| Path | Risk without mTLS | mTLS mitigation |
|------|-------------------|-----------------|
| Internet → Caddy | Credential sniffing, MITM | Public TLS (ACME or corporate CA) |
| Caddy → hybrid-rag-query | Lateral movement on internal net | Upstream client cert + CA verify |
| Query → Qdrant/Neo4j/Postgres | Store credential replay | Service mesh or store-native TLS |

**Scope of this doc:** Caddy edge + upstream mTLS. For full mesh, see §4.

---

## 2. Caddy upstream mTLS (recommended first step)

Enable in `config/infra.toml`:

```toml
[caddy]
enabled = true
site_name = "rag.example.com"
tls = true
mcp_upstream = "https://127.0.0.1:8010"

[caddy.mtls]
enabled = true
upstream_ca = "/etc/caddy/certs/ca.crt"
upstream_cert = "/etc/caddy/certs/caddy-client.crt"
upstream_key = "/etc/caddy/certs/caddy-client.key"
```

Render:

```bash
make -C infra render-caddy
```

The generated Caddyfile adds `transport http { tls … tls_client_auth … }` on every `reverse_proxy` block. See `caddy/Caddyfile.mtls.example`.

**Query side:** run MCP HTTP with TLS and require client certificates when `MCP_MTLS_ENABLED=true`:

```bash
# query/.env
MCP_MTLS_ENABLED=true
MCP_TLS_CERT=/etc/query/certs/server.crt
MCP_TLS_KEY=/etc/query/certs/server.key
MCP_TLS_CLIENT_CA=/etc/query/certs/client-ca.crt   # require Caddy client cert
```

Start listener:

```bash
python -m app.server   # Dockerfile CMD; honors MCP_MTLS_*
```

`/healthz` reports `"mtls_enabled": true` when active.

---

## 3. Edge client certificate authentication (optional)

Require callers to present a client cert before reaching MCP routes:

```toml
[caddy.mtls]
client_auth = true
client_ca = "/etc/caddy/certs/client-ca.crt"
```

Rendered site block:

```caddyfile
tls ops@example.com {
    client_auth {
        mode require_and_verify
        trust_pool file /etc/caddy/certs/client-ca.crt
    }
}
```

Pair with JWT/`mcp_bearer_token` for defense in depth — mTLS identifies the integration, bearer/JWT identifies the tenant.

---

## 4. Service mesh option (Linkerd / Istio)

When Caddy upstream mTLS is insufficient (query → Qdrant, ingest → MinIO, cross-AZ traffic):

| Approach | When | Notes |
|----------|------|-------|
| **Linkerd** | K8s, minimal config | Auto mTLS between meshed pods; annotate `hybrid-rag-query` Deployment |
| **Istio** | Existing Istio estate | `PeerAuthentication` STRICT + `DestinationRule` for external stores |
| **Store-native TLS** | Managed Qdrant/Neo4j/Postgres | Prefer provider TLS endpoints; set `bolt+s://`, `rediss://` in Helm `values-prod.yaml` |

Helm sketch: enable mesh injection via pod annotations (not rendered by default):

```yaml
query:
  podAnnotations:
    linkerd.io/inject: enabled
```

**Anti-pattern:** mTLS only at Caddy while query talks to Qdrant in cleartext on a shared VPC — acceptable for dev, not for regulated prod.

---

## 5. Certificate rotation

| Tier | Rotation cadence | Procedure |
|------|------------------|-----------|
| Public edge (Caddy) | ACME auto or 90d | Caddy reload |
| Caddy → query client cert | 90d | Rolling query + Caddy reload |
| Mesh identity | Automatic (Linkerd) | N/A |

Document issuer (`internal`, corporate PKI, cert-manager `Certificate` CR) in your runbook. See [`CERT_MANAGER.md`](./CERT_MANAGER.md) for install and Helm integration.

---

## 6. Validation

```bash
make validate-p2          # contract tests E-34
make -C infra render-caddy
make -C infra mtls-dev-certs   # local compose PKI
make -C infra cert-manager-install cert-manager-issuer   # Kubernetes PKI
caddy validate --config infra/caddy/Caddyfile
```

**Dev cert layout** (`make -C infra mtls-dev-certs`):

| File | Mount / env |
|------|-------------|
| `server.crt` / `server.key` | `MCP_TLS_CERT` / `MCP_TLS_KEY` on query |
| `client-ca.crt` | `MCP_TLS_CLIENT_CA` (require Caddy client cert) |
| `caddy-client.crt` / `.key` | Caddy `[caddy.mtls] upstream_cert` / `upstream_key` |
| `ca.crt` | Caddy `upstream_ca` |

Compose edge profile mounts `infra/certs/dev` at `/etc/caddy/certs`.

**Smoke:** `curl --cert client.crt --key client.key --cacert ca.crt https://127.0.0.1:8443/healthz`
