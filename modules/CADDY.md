# Caddy — moved to infrastructure sub-project

TLS edge and MCP SSE reverse proxy are owned by **`hybrid-rag-infra`**.

| Document | Path |
|----------|------|
| Caddy spec | [../infra/docs/CADDY.md](../infra/docs/CADDY.md) |
| Infra README | [../infra/README.md](../infra/README.md) |
| Integration | [../infra/docs/INTEGRATION.md](../infra/docs/INTEGRATION.md) |

```bash
cd infra && make render-caddy && make up PROFILE=edge
```
