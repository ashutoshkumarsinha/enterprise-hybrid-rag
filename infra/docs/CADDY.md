# Caddy Edge Proxy (hybrid-rag-infra)

**Owner:** `hybrid-rag-infra`  
**Profile:** `edge` (`make up PROFILE=edge`)

Caddy is the **TLS termination and public edge** for the query module's MCP HTTP surface. It does **not** proxy Qdrant, Neo4j, Redis, MinIO, vLLM, or Langfuse to the public internet.

---

## 1. What Caddy exposes

| Path | Backend | Purpose |
|------|---------|---------|
| `{site}{mcp_path}/sse` | `hybrid-rag-query` MCP SSE (`:8010`) | MCP + `/research/stream` |
| `{site}{mcp_path}/healthz` | same upstream | Public health (optional) |

**Data plane stays on internal network** — Docker `hybrid-rag-net` or localhost only.

---

## 2. Configuration (`config/infra.toml`)

```toml
[caddy]
enabled = true
bind_ip = "0.0.0.0"
http_port = 8080
https_port = 443
site_name = "rag.example.com"
email = "ops@example.com"
tls = true
proxy_mcp = true
mcp_path = "/mcp"
mcp_upstream = "127.0.0.1:8010"
mcp_bearer_token = ""
```

Render Caddyfile:

```bash
make render-caddy
```

---

## 3. SSE-critical settings

| Directive | Value | Why |
|-----------|-------|-----|
| `flush_interval -1` | disable buffering | Low TTFT for token stream |
| `transport http { versions 1.1 }` | HTTP/1.1 | SSE compatibility |
| `handle_path /mcp/*` | strip prefix | Upstream sees `/sse` not `/mcp/sse` |

---

## 4. Authentication (production)

| Layer | Mechanism |
|-------|-----------|
| Caddy | `Authorization: Bearer <mcp_bearer_token>` on `/mcp/*` |
| hybrid-rag-query | JWT `tenant_id` on application routes |

---

## 5. Public URLs

| Environment | MCP SSE URL |
|-------------|-------------|
| Dev (no Caddy) | `http://127.0.0.1:8010/sse` |
| Prod HTTP | `http://<host>:8080/mcp/sse` |
| Prod HTTPS | `https://rag.example.com/mcp/sse` |

---

## 6. Port matrix

| Service | Port | Via Caddy? |
|---------|------|------------|
| Caddy HTTP | 8080 / 443 | — |
| hybrid-rag-query MCP | 8010 | yes (`/mcp/*`) |
| Qdrant | 6333 | **no** |
| Inference | 8000+ | **no** |

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| SSE stalls | Re-render with `flush_interval -1` |
| 401 on MCP | Align BFF bearer + `mcp_bearer_token` |
| 502 | Ensure hybrid-rag-query listening on `mcp_upstream` |
