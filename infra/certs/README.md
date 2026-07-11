# Dev mTLS certificates

Generated locally by `make -C infra mtls-dev-certs` (not committed — `*.crt` / `*.key` are gitignored).

| File | Use |
|------|-----|
| `ca.crt` | Trust anchor for Caddy upstream verify |
| `server.crt` / `server.key` | Query MCP listener (`MCP_TLS_*`) |
| `caddy-client.crt` / `.key` | Caddy → query client cert |
| `client-ca.crt` | Query client-auth CA (`MCP_TLS_CLIENT_CA`) |

See [`../docs/MTLS.md`](../docs/MTLS.md).
