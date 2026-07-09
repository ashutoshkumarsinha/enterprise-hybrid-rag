# Shared Contracts (`mod-kernel`)

**Version:** 1.0  
**Consumers:** `hybrid-rag-ingest` (writer), `hybrid-rag-query` (reader)  
**Rule:** No runtime service. Schema + events + API types only. Breaking changes require `index_schema_version` bump.

Parent: [ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md) §4

---

## 1. Purpose

The kernel is the **only** coupling surface between ingestion and query modules. Teams may ship `hybrid-rag-ingest` and `hybrid-rag-query` on different release trains if they honor these contracts.

---

## 2. Index schema version

```toml
# config/query.toml and config/ingest.toml — MUST match
index_schema_version = 1
embed_dimension = 768
qdrant_collection = "enterprise_hybrid_rag"
sparse_vector_name = "bm25-text"
```

**JSON schemas:** [`schemas/`](./schemas/) — `chunk_payload.v1.json`, MCP inputs, events (spec §4.7).

On breaking payload changes: increment version, run full reindex, deploy query before ingest or gate on version check.

---

## 3. Chunk payload (Qdrant)

Normative field list: parent spec §4.2. Required filters: `tenant_id`, `collection_id`, `document_id`, `version_id`, `type`.

**Writer:** `hybrid-rag-ingest` via `upsert_points`.  
**Reader:** `hybrid-rag-query` via hybrid search + payload filters.

---

## 4. Graph schema (Neo4j)

Normative: parent spec §4.3.  
**Writer:** `hybrid-rag-ingest` MERGE/UNWIND.  
**Reader:** `hybrid-rag-query` read-only Cypher for graph enrich.

---

## 5. Catalog tables (Postgres)

| Table | ingest | query |
|-------|--------|-------|
| `tenants` | R | R |
| `collections` | RW | R |
| `documents` | RW | R |
| `document_versions` | RW | R |
| `ingest_jobs` | RW | R (status only) |
| `acl_grants` | RW | R |
| `conversation_sessions` | — | RW (`query_session_rw`) |
| `conversation_messages` | — | RW (`query_session_rw`) |

**DSN split:**

- `CATALOG_DSN` — ingest (read-write)
- `CATALOG_DSN_RO` — query catalog read (`query_ro`)
- `CATALOG_DSN_SESSION` — query session read-write (`query_session_rw`) — §7.11, §4.4.2

---

## 6. Redis key namespaces

| Namespace | Owner | Purpose |
|-----------|-------|---------|
| `dedup:{tenant}:{hash}` | ingest | Chunk dedup |
| `file:{tenant}:{collection}:{path}` | ingest | Incremental registry |
| `qcache:{sha256}` | query | Result cache |
| `embedcache:{sha256}` | query | Optional embed vector cache |
| `rlimit:{tenant}:queries` | query | Tenant query rate limit |
| `rlimit:{tenant}:{sub}:queries` | query | Per-user query rate limit |
| `rlimit:{tenant}:streams` | query | Concurrent SSE counter |
| `rag:events` | ingest → query | Domain event stream |

Query module MUST NOT write `dedup:` or `file:` keys.

---

## 7. Domain events

Normative: parent spec §3.3 IF-3. Transport: Redis Stream `rag:events` (default) or HTTP webhook (`INGEST_EVENT_WEBHOOK_URL`).

### `ingest.completed`

```json
{
  "event": "ingest.completed",
  "schema_version": 1,
  "tenant_id": "acme-corp",
  "collection_id": "payments-api",
  "version_id": "2026-03-01",
  "job_id": "uuid",
  "chunk_count": 12400,
  "error_count": 0,
  "cache_bump": true,
  "timestamp": "2026-07-09T20:00:00Z"
}
```

**Query subscriber:** if `cache_bump`, call `bump_cache_version(tenant_id, collection_id)`.

### `ingest.failed`

```json
{
  "event": "ingest.failed",
  "job_id": "uuid",
  "tenant_id": "acme-corp",
  "collection_id": "payments-api",
  "error": "string"
}
```

### `acl.changed`

```json
{
  "event": "acl.changed",
  "tenant_id": "acme-corp",
  "collection_id": "payments-api",
  "principal": "group:payments-team"
}
```

**Query subscriber:** flush in-process ACL LRU for tenant.

---

## 8. Identity principals and RBAC (IF-6)

JWT `sub` from Keycloak maps to catalog/Qdrant principal `user:{sub}`. Realm roles map to `group:{role}` for ACL and to **permission strings** for MCP RBAC (§7.13).

| Concept | Source | Used for |
|---------|--------|----------|
| `user:{sub}` | JWT `sub` | Session ownership, ACL |
| `group:{role}` | `realm_access.roles` | ACL grants on collections |
| `group:{name}` | JWT `groups` claim (optional) | ACL team membership |
| `service:{client_id}` | `azp` / client credentials | Automation principals |
| `mcp.research`, etc. | Role → permission map in `query.toml` | Tool authorization |

Query MUST: (1) resolve permissions from roles before MCP handler, (2) resolve principals before ACL filter construction. Ingest writes `acl_principal` on chunks when document-level ACL is set.

See [query/docs/RBAC.md](../query/docs/RBAC.md) and platform §7.13, §9.4.

---

## 9. Object store layout (MinIO)

**Buckets:** `hybrid-rag` (primary), `hybrid-rag-staging` (multipart / scratch) — provisioned by `infra/scripts/init-minio.sh`.

```text
{bucket}/{tenant_id}/{collection_id}/{document_id}/{version_id}/{object_kind}/{uuid}.{ext}
```

| `object_kind` | Content |
|---------------|---------|
| `raw` | Original PDF, DOCX, HTML export |
| `images` | Extracted figures, diagrams (PNG/WebP/SVG) |
| `thumbnails` | Downscaled previews for UI |
| `exports` | Admin bundle exports |

Ingest writes objects; query resolves `image_url` in chunk payload to a **presigned GET** (object key stored in Qdrant, URL generated at answer time).

See [infra/docs/MINIO.md](../infra/docs/MINIO.md).

---

## 12. Tenant quotas (catalog)

Table `tenant_quotas` (Postgres, written by admin API):

| Column | Type | Description |
|--------|------|-------------|
| `tenant_id` | text PK | Tenant identifier |
| `tier` | enum | `standard` \| `professional` \| `regulated` |
| `max_chunks` | bigint | Total indexed chunks |
| `max_collections` | int | Collection count |
| `query_qps` | float | Max queries per second (admission) |
| `max_concurrent_streams` | int | SSE concurrency cap |
| `max_storage_bytes` | bigint | MinIO prefix total |
| `max_embed_tokens_day` | bigint | Daily embed token budget |

Query reads for admission (FR-27, FR-30); ingest reads before enqueue. Overrides platform defaults in §9.3.

**Regulated tier:** optional `qdrant_collection_suffix` for dedicated collection per tenant.

---

## 13. Compatibility matrix

| ingest version | query version | index_schema_version | Compatible |
|----------------|---------------|----------------------|------------|
| 1.x | 1.x | 1 | yes |
| 2.x (new payload field) | 1.x | 1 | yes if optional field |
| 2.x (rename field) | 1.x | 1 | **no** — bump schema version |

---

## 14. Contract tests & TDD (kernel)

Normative methodology: platform §19 · [docs/TESTING.md](../docs/TESTING.md)

**Order:** schema/fixture → failing test → implementation (FR-33, FR-34, TL-11).

| Test | Validates | Tier |
|------|-----------|------|
| `test_chunk_payload_schema.py` | Ingest output matches JSON schema | contract / PR |
| `test_query_reads_ingest_fixture.py` | Query retrieves seeded ingest corpus | integration / nightly |
| `test_event_cache_bump.py` | `ingest.completed` invalidates query cache | contract / PR |
| `test_catalog_ro_role.py` | Query DSN cannot INSERT | contract / PR |
| `test_mcp_markdown_contract.py` | Answer + Sources + telemetry footer order | contract / PR |
| `test_sse_event_contract.py` | SSE types: token, sources, telemetry, done, error | contract / PR |
| `test_tenant_filter_enforced.py` | No cross-tenant retrieval | integration / nightly |

Run **unit + contract** on every PR; **integration** after both sub-project unit suites pass (`LIVE_STACK=1`).

Planned schemas: `modules/schemas/chunk_payload.v1.json`, `golden_set.schema.json`.
