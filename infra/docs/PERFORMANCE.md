# Infrastructure Performance — hybrid-rag-infra

**Parent:** [ENTERPRISE_HYBRID_RAG_SPEC.md](../../ENTERPRISE_HYBRID_RAG_SPEC.md) §12.2–12.3, §18.11  
**Platform guide:** [PERFORMANCE.md](../../docs/PERFORMANCE.md)

The infra sub-project has **no custom application runtime** — performance is achieved by **store tuning**, **resource sizing**, **network placement**, and **write/read isolation**.

---

## 1. Optimization hierarchy (infra)

```text
1. Payload indexes + filter fields     tenant_id, collection_id on Qdrant
2. on_disk_payload + search_ef         Qdrant RAM vs latency
3. Neo4j heap/pagecache                graph read latency during query
4. Redis DB separation                 broker vs cache eviction policy
5. Postgres indexes + connection caps  catalog lookup p95
6. Caddy SSE tuning                    edge TTFT for public MCP
7. Off-peak write windows              ingest bulk vs query retrieve
```

---

## 2. Qdrant

Detail: [QDRANT.md](./QDRANT.md)

| Corpus | `search_ef` | `hnsw_m` | `on_disk_payload` | Quantization |
|--------|-------------|----------|-------------------|--------------|
| < 100k | 128 | 16 | recommended | optional |
| 100k–500k | 128–192 | 16 | **required** | optional INT8 |
| 500k–2M | 192–256 | 24 | **required** | INT8 recommended |
| > 2M | 256+ | 32 | **required** | INT8 + shard plan |

**Query path (consumer guidance):**

- Prefer **gRPC** `:6334` over REST `:6333`
- Always filter `tenant_id` + `collection_id` before fusion
- Create payload indexes on: `tenant_id`, `collection_id`, `document_id`, `version_id`, `type`, `acl_principal`

**Ingest path:**

- `qdrant_upsert_batch = 100` (ingest config)
- Bulk upserts with `wait=false` during large reindex — query sees points within seconds
- Schedule full reindex off-peak (NFR-18)

**Health SLO:** `GET /readyz` < 50ms; search p95 < 200ms at target `search_ef`.

---

## 3. Neo4j

| Deployment | `heap_max` | `pagecache` | When |
|------------|------------|-------------|------|
| Dev | 2G | 512m | Default compose |
| Prod | 4G | 2G | > 1M nodes |
| Large + fulltext | 8G | 4G | `neo4j_fulltext_enabled` |

**Query:** read-only Bolt sessions; graph enrich limited to `rerank_top_k` chunk ids — no full-graph scans.

**Ingest:** `neo4j_unwind_batch = 50`; avoid per-node MERGE in loops.

**Anti-pattern:** enabling fulltext index on every collection without measuring recall lift (adds ingest + query cost).

Config: `config/infra.toml` → `[neo4j]`.

---

## 4. Redis

| DB | Use | Eviction | Performance note |
|----|-----|----------|------------------|
| 0 | Query cache, `rag:events` | `allkeys-lru` if memory-bound | Set `maxmemory`; monitor hit rate |
| 1 | Celery broker | **no eviction** | Dedicated memory; never share with cache |
| 2 | Dedup + file registry | no eviction | MGET batches in ingest (`dedup_mget_batch`) |

**Latency target:** `PING` < 1ms; `MGET` 100 keys < 5ms on same host.

**Prod:** pin Redis to fast disk (AOF optional); avoid broker on network storage.

---

## 5. Postgres (catalog)

**Roles:** `ingest_rw` (write), `query_ro` (read-only) — provisioned at init.

**Indexes (ingest migrations + INF-P2):**

Base indexes in `ingest/migrations/001_catalog_v1.sql`. Supplemental performance indexes in `infra/scripts/postgres-catalog-indexes.sql` — apply via `make -C infra init-catalog-indexes` after migrations.

```sql
CREATE INDEX idx_acl_grants_principal ON acl_grants (tenant_id, principal);
CREATE INDEX idx_documents_tenant_collection_doc ON documents (tenant_id, collection_id, document_id);
```

**Connection guidance for consumers:**

| Consumer | Pool | Notes |
|----------|------|-------|
| query | 5 + 10 overflow | batch catalog lookups in rerank context assembly |
| ingest | 5 + 10 overflow | job status updates only |

**Keycloak DB:** separate `keycloak` database on same Postgres host — isolate connection pools from catalog.

---

## 6. MinIO (documents, images, thumbnails)

- **Buckets:** `hybrid-rag` (primary), `hybrid-rag-staging` (multipart scratch) — `make init-minio`
- **Path kinds:** `raw/`, `images/`, `thumbnails/` under tenant/collection/document/version
- Presigned URLs in chunk payloads — query never proxies blob bytes through MCP
- Ingest: multipart upload for large PDFs; stage in `hybrid-rag-staging` then promote
- **Prod:** local SSD or dedicated object tier; avoid NFS for hot paths

Detail: [MINIO.md](./MINIO.md)

---

## 7. Keycloak

- Dev: `start-dev` in compose — not for load testing
- **Prod:** `start` mode, `KC_HOSTNAME` set, connection pool to Postgres
- JWKS cache in query app (≤ 1h) — Keycloak not on query hot path per request if cached

**Not a query latency concern** when OIDC handled at BFF; query validates JWT locally.

---

## 8. Caddy (edge profile)

| Setting | Recommendation |
|---------|----------------|
| `flush_interval` | `-1` for SSE (disable buffering) |
| `reverse_proxy` | HTTP/1.1 keep-alive to `query:8010` |
| TLS | terminate at Caddy; internal mesh HTTP |

**SSE MCP:** buffering at edge adds TTFT — Caddyfile MUST disable response buffering on `/mcp/sse`.

See [CADDY.md](./CADDY.md).

---

## 9. Docker / network

- All services on `hybrid-rag-net` — avoid host port hairpin for inter-container calls
- **Do not** expose Qdrant, Neo4j, Redis, Postgres on public internet
- Co-locate query + stores on same host/AZ for < 1ms RTT where possible

---

## 10. Resource profiles (`config/infra.toml` → `[performance]`)

| Profile | Qdrant RAM | Neo4j heap | Redis maxmemory |
|---------|------------|------------|-----------------|
| `dev` | 4 GB | 2G | 256mb |
| `prod_500k` | 16 GB | 4G | 1gb |
| `prod_2m` | 32 GB | 8G | 2gb |

---

## 11. Planned optimizations (roadmap)

| ID | Optimization | Status |
|----|--------------|--------|
| INF-P1 | Qdrant INT8 quantization init script | **Done** — `init-db.sh` + `QDRANT_INT8_QUANTIZATION` |
| INF-P2 | Postgres catalog index DDL in `init-db.sh` | **Done** — `scripts/postgres-catalog-indexes.sql` + `init-catalog-indexes` |
| INF-P3 | Redis `maxmemory` + LRU in compose | **Done** — `REDIS_MAXMEMORY` / `REDIS_MAXMEMORY_POLICY` in compose |
| INF-P4 | Caddy SSE `flush_interval -1` in `Caddyfile.example` | **Done** — `/mcp/*` + `/research/stream` |
| INF-P5 | Qdrant gRPC port 6334 exposed in compose docs | **Done** — compose + `PREFER_QDRANT_GRPC` consumer env |
| INF-P6 | Neo4j read replica notes for scale-out | future |

**v1.0 gate:** INF-P1–P4 MUST be implemented before `infra-v1.0` tag.

---

## 13. Compression and resilience

| Technique | When | Impact |
|-----------|------|--------|
| Qdrant INT8 (INF-P1) | > 500k chunks | ~50% RAM reduction |
| MinIO gzip `raw/` | exports > 64 KB | Egress savings |
| Redis Sentinel | prod broker HA | Ingest continuity |
| Qdrant read replica | search QPS > 500/s | Query scale-out (INF-P6) |

---

## 14. Health & benchmarks

```bash
cd infra && make health
```

**Store SLOs (single-node prod):**

| Store | Check | Target |
|-------|-------|--------|
| Qdrant | `/readyz` | < 50ms |
| Neo4j | HTTP 7474 | up |
| Redis | `PING` | < 1ms |
| Postgres | `pg_isready` | up |

Integration benchmarks in query/ingest sub-projects measure end-to-end impact of infra tuning — commit `baselines.json` per profile after infra changes.
