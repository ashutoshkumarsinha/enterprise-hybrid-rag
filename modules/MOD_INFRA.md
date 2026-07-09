# Infrastructure — moved to sub-project

The data plane and TLS edge live in **`hybrid-rag-infra`**.

| Document | Path |
|----------|------|
| Sub-project README | [../infra/README.md](../infra/README.md) |
| Specification | [../infra/SPEC.md](../infra/SPEC.md) |
| Qdrant | [../infra/docs/QDRANT.md](../infra/docs/QDRANT.md) |
| Neo4j | [../infra/docs/NEO4J.md](../infra/docs/NEO4J.md) |
| Redis | [../infra/docs/REDIS.md](../infra/docs/REDIS.md) |
| MinIO | [../infra/docs/MINIO.md](../infra/docs/MINIO.md) |
| Postgres catalog | [../infra/docs/POSTGRES.md](../infra/docs/POSTGRES.md) |
| Keycloak OIDC | [../infra/docs/KEYCLOAK.md](../infra/docs/KEYCLOAK.md) |
| Implementation languages | [../modules/IMPLEMENTATION.md](../modules/IMPLEMENTATION.md) |
| Caddy edge | [../infra/docs/CADDY.md](../infra/docs/CADDY.md) |
| RAG integration | [../infra/docs/INTEGRATION.md](../infra/docs/INTEGRATION.md) |

**Project ID:** `hybrid-rag-infra`  
**Deploy:** `cd infra && make up && make init-db`  
**Consumers:** `hybrid-rag-query`, `hybrid-rag-ingest` — client libraries + connection URLs only.
