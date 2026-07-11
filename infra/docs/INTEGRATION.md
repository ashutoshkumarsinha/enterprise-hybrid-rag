# Integration Guide — RAG Platform ↔ Infrastructure Sub-Project

How **hybrid-rag-query** and **hybrid-rag-ingest** connect to `hybrid-rag-infra` without embedding store server code.

---

## 1. Network topology

```mermaid
flowchart TB
    Q[hybrid-rag-query]
    ING[hybrid-rag-ingest]
    CHAT[mod-chat optional]
    INF["hybrid-rag-infra<br/>Qdrant Neo4j Redis MinIO Postgres Keycloak Caddy"]

    Q -->|read/write URLs| INF
    ING --> INF
    CHAT -->|OIDC| INF
```

All stacks share Docker network **`hybrid-rag-net`**:

```bash
cd infra && make network && make up
cd ../inference && make up PROFILE=gpu_24gb
cd ../observability && make up
```

---

## 2. Environment variables (applications)

### hybrid-rag-query

```bash
QDRANT_URL=http://qdrant:6333
QDRANT_GRPC_PORT=6334
PREFER_QDRANT_GRPC=true
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
REDIS_URL=redis://redis:6379/0
CATALOG_DSN_RO=postgresql://query_ro:...@postgres:5432/catalog
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=hybrid-rag-query
MINIO_SECRET_KEY=...
MINIO_BUCKET=hybrid-rag
MINIO_PRESIGN_TTL_SECONDS=3600
```

### hybrid-rag-ingest

```bash
QDRANT_URL=http://qdrant:6333
QDRANT_GRPC_PORT=6334
PREFER_QDRANT_GRPC=true
NEO4J_URI=bolt://neo4j:7687
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=hybrid-rag-ingest
MINIO_SECRET_KEY=...
MINIO_BUCKET=hybrid-rag
MINIO_BUCKET_STAGING=hybrid-rag-staging
CATALOG_DSN=postgresql://ingest_rw:...@postgres:5432/catalog
```

### mod-chat (optional)

```bash
CATALOG_DSN=postgresql://...@postgres:5432/catalog   # threads only
MCP_SSE_URL=https://rag.example.com/mcp/sse          # via Caddy edge
KEYCLOAK_URL=http://keycloak:8080
OIDC_ISSUER=http://keycloak:8080/realms/hybrid-rag
OIDC_CLIENT_ID=mod-chat
```

Detail: [KEYCLOAK.md](./KEYCLOAK.md)

---

## 3. Shared invariants

Must match across `infra/config/infra.toml`, `query.toml`, and `ingest.toml`:

| Key | Example |
|-----|---------|
| `embed_dimension` | `768` |
| `qdrant_collection` | `enterprise_hybrid_rag` |
| `index_schema_version` | `1` |

---

## 4. Bootstrap order

1. `cd infra && make up && make init-db`  # includes MinIO buckets + IAM
2. Run hybrid-rag-ingest migrations (catalog tables)
3. `cd inference && make up` (embed model must match dimension)
4. Start `hybrid-rag-ingest`, then hybrid-rag-query
5. Optional: `cd infra && make up PROFILE=edge` for public MCP

---

## 5. Health dependencies

`hybrid-rag-query` `/healthz` `research_ready` requires:

- Qdrant collection exists
- Postgres catalog reachable
- Inference chat + embed URLs (separate sub-project)

Store-only health: `cd infra && make health`

---

## 6. Compatibility matrix

| infra tag | index_schema_version | Notes |
|-----------|---------------------|-------|
| infra-v1.0.0 | 1 | Initial Qdrant sparse + dense |
| infra-v1.1.0 | 2 | Breaking payload change (example) |

Bump `index_schema_version` in all three configs when ingest changes chunk payload shape.

---

## 7. Laptop dev without Docker

Point application configs at managed services or local installs — same URL keys, different hosts. Inference may use Ollama fallback per parent spec §5A.
