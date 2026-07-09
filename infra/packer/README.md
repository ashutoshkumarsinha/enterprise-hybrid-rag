# Packer — hybrid-rag-infra

Mirrors pinned upstream store images to `hybrid-rag-*` names (no custom Dockerfile).

| Output image | Upstream |
|--------------|----------|
| `hybrid-rag-qdrant` | `qdrant/qdrant:v1.12.5` |
| `hybrid-rag-neo4j` | `neo4j:5.26-community` |
| `hybrid-rag-redis` | `redis:7-alpine` |
| `hybrid-rag-minio` | `minio/minio:RELEASE.2024-12-18T13-15-44Z` |
| `hybrid-rag-postgres` | `postgres:16-alpine` |
| `hybrid-rag-caddy` | `caddy:2.8-alpine` |
| `hybrid-rag-keycloak` | `quay.io/keycloak/keycloak:26.0` |

```bash
make packer-build IMAGE_TAG=infra-v1.0.0
```

See [../../packer/README.md](../../packer/README.md).
