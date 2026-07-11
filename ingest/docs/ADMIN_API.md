# Admin API (hybrid-rag-ingest)

**Port:** 8020 (orchestrator)  
**Auth:** Service account JWT or mTLS — not end-user OIDC

## Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/admin/ingest/collection` | POST | Enqueue connector sync (S3/filesystem) |
| `/admin/connectors/sync` | POST | Alias for collection connector sync |
| `/admin/ingest/document` | POST | Single document ingest |
| `/admin/ingest/jobs/{id}` | GET | Job status |
| `/admin/acl/grants` | POST | Create principal grant (collection or document scope) |
| `/admin/acl/grants` | GET | List grants (`tenant_id` required; optional `principal`, `collection_id`) |
| `/admin/acl/grants/{grant_id}` | DELETE | Revoke grant |
| `/admin/collections/{tenant_id}/{collection_id}/default_acl` | PATCH | Update collection `default_acl` JSON array |
| `/admin/healthz` | GET | Worker + broker + store write probe |

## Not exposed

- `/research/stream`
- MCP SSE
- Query or chat routes

## Example: collection job

```bash
curl -sf -X POST http://localhost:8020/admin/ingest/collection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INGEST_SERVICE_TOKEN" \
  -d '{
    "tenant_id": "acme-corp",
    "collection_id": "payments-api",
    "version_id": "2026-03-01",
    "mode": "incremental"
  }'
```

## Example: ACL grant

```bash
curl -sf -X POST http://localhost:8020/admin/acl/grants \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INGEST_SERVICE_TOKEN" \
  -d '{
    "tenant_id": "acme-corp",
    "principal": "group:payments-team",
    "collection_id": "payments-api",
    "permission": "read"
  }'
```

## Health response

```json
{
  "status": "ok",
  "module": "hybrid-rag-ingest",
  "checks": {
    "celery_ok": true,
    "redis_broker_ok": true,
    "qdrant_write_ok": true,
    "neo4j_write_ok": true,
    "catalog_ok": true,
    "inference_embed_ok": true
  }
}
```

## Ingest modes

| Mode | Trigger |
|------|---------|
| Full | New `version_id`; re-index entire collection |
| Incremental | File registry hash diff |
| Single document | `POST /admin/ingest/document` |
| Connector sync | Celery beat schedule |
