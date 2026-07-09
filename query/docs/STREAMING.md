# SSE streaming (`POST /research/stream`)

**Consumer:** mod-chat BFF, internal APIs  
**Owner:** hybrid-rag-query

## Event types (FR-05)

Only these JSON event shapes in the SSE stream:

| `type` | Payload |
|--------|---------|
| `token` | `{ "type": "token", "content": "..." }` |
| `sources` | `{ "type": "sources", "sources": [...] }` |
| `telemetry` | `{ "type": "telemetry", "timings_ms": {...}, ... }` |
| `done` | `{ "type": "done" }` |
| `error` | `{ "type": "error", "message": "...", "kind": "..." }` |

## Example request

```bash
curl -N -X POST http://localhost:8010/research/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the rate limit?",
    "tenant_id": "acme-corp",
    "collection_id": "payments-api"
  }'
```

## TTFT optimization

Stream starts after retrieve + rerank complete; tokens follow as LLM generates. Caddy MUST use `flush_interval -1` on MCP/SSE proxy (see `infra/docs/CADDY.md`).

## Contract tests

CI validates SSE JSON shape against frozen fixtures — no extra event types.
