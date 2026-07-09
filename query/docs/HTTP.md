# HTTP routes (hybrid-rag-query)

**Port:** 8010

## Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/healthz` | GET | Store + inference readiness |
| `/research/stream` | POST | SSE token stream |
| `/sse` | GET | MCP SSE transport |

## Health schema

```json
{
  "status": "ok",
  "research_ready": true,
  "stores_ready": true,
  "checks": {
    "qdrant_ok": true,
    "neo4j_ok": true,
    "redis_ok": true,
    "inference_ok": true,
    "catalog_ok": true
  }
}
```

`research_ready` is true only when inference + Qdrant + catalog are reachable (FR-06).

Health MUST NOT require Celery or ingest orchestrator.

## Error kinds

| Kind | HTTP | Pattern |
|------|------|---------|
| `scope_resolution` | 422 | Cannot determine documents to search |
| `validation` | 400 | Invalid argument |
| `not_found` | 404 | Collection/document not indexed |
| `inference` | 503 | AI backend unavailable |
| `internal` | 500 | No stack trace to client |

## Auth (production)

| Layer | Mechanism |
|-------|-----------|
| Caddy | Bearer on `/mcp/*` |
| Application | JWT `tenant_id` on routes |

Dev: direct `http://127.0.0.1:8010` without bearer.
