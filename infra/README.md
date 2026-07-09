# Enterprise Hybrid RAG — Infrastructure Sub-Project

**Project ID:** `hybrid-rag-infra`  
**Independent deployable** from query, ingest, inference, and observability.

Hosts the **data plane**, **identity (Keycloak)**, and **TLS edge** for the platform:

| Service | Default port | Role |
|---------|--------------|------|
| **Qdrant** | 6333 / 6334 | Hybrid vector index |
| **Neo4j** | 7687 | Document graph + fulltext |
| **Redis** | 6379 | Celery broker, dedup, query cache |
| **MinIO** | 9000 / 9001 | Object store (PDFs, images) |
| **Postgres** | 5432 | Catalog, ACL, ingest jobs |
| **Keycloak** | 8081 | OIDC identity (`hybrid-rag` realm) |
| **Caddy** | 8080 / 443 | MCP SSE reverse proxy (optional profile) |

Parent platform: [../ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md)

## Documents

| Document | Description |
|----------|-------------|
| [SPEC.md](./SPEC.md) | Sub-project boundary, ports, profiles |
| [docs/QDRANT.md](./docs/QDRANT.md) | Collection schema, HNSW, init |
| [docs/NEO4J.md](./docs/NEO4J.md) | Graph schema, JVM sizing |
| [docs/REDIS.md](./docs/REDIS.md) | Broker, cache keys, streams |
| [docs/MINIO.md](./docs/MINIO.md) | Buckets, presigned URLs |
| [docs/POSTGRES.md](./docs/POSTGRES.md) | Catalog DB, roles |
| [docs/KEYCLOAK.md](./docs/KEYCLOAK.md) | OIDC realm, clients, mod-chat integration |
| [docs/CADDY.md](./docs/CADDY.md) | TLS edge, MCP proxy |
| [docs/PERFORMANCE.md](./docs/PERFORMANCE.md) | Store tuning, Redis, Caddy SSE |
| [docs/INTEGRATION.md](./docs/INTEGRATION.md) | How query & ingest connect |

## Quick start

```bash
cd infra
cp .env.example .env
cp config/infra.toml.example config/infra.toml
make network
make up
make init-db      # Qdrant collection + MinIO buckets/IAM
make init-minio   # MinIO only (re-run safe)
make health
```

Optional MCP edge:

```bash
make up PROFILE=edge
```

## Consumer URLs (application env)

```bash
# hybrid-rag-query
QDRANT_URL=http://qdrant:6333
NEO4J_URI=bolt://neo4j:7687
REDIS_URL=redis://redis:6379/0
CATALOG_DSN_RO=postgresql://query_ro:...@postgres:5432/catalog

# hybrid-rag-ingest
QDRANT_URL=http://qdrant:6333
NEO4J_URI=bolt://neo4j:7687
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=hybrid-rag-ingest
MINIO_SECRET_KEY=change-me-ingest-minio
MINIO_BUCKET=hybrid-rag
CATALOG_DSN=postgresql://ingest_rw:...@postgres:5432/catalog

# hybrid-rag-query (presigned image URLs)
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=hybrid-rag-query
MINIO_SECRET_KEY=change-me-query-minio
MINIO_BUCKET=hybrid-rag
MINIO_PRESIGN_TTL_SECONDS=3600

# mod-chat (optional)
KEYCLOAK_URL=http://keycloak:8080
OIDC_ISSUER=http://keycloak:8080/realms/hybrid-rag
OIDC_CLIENT_ID=mod-chat
```

`embed_dimension` and `qdrant_collection` in app configs **must match** `config/infra.toml`.

## Repository layout

```text
enterprise-hybrid-rag/
├── query/          # read stores + catalog RO
├── ingest/         # hybrid-rag-ingest — write stores + catalog RW
├── inference/      # model serving (separate sub-project)
├── observability/  # telemetry (separate sub-project)
└── infra/          # ← this sub-project (infra-v*)
```

**Versioning:** Tag `infra-v1.x` independently of `rag-v1.x`.
