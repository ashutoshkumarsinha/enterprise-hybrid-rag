# deploy/helm — Enterprise Hybrid RAG (E-19)

Kubernetes Helm sketch for production split-deploy (spec §12.4, OD6).

## Chart

| Path | Purpose |
|------|---------|
| `hybrid-rag/Chart.yaml` | Umbrella application chart |
| `hybrid-rag/values.yaml` | Defaults (self-hosted store URLs) |
| `hybrid-rag/values-prod.yaml` | Prod overlay — managed stores, HPA, mod-chat |

## Components

| Workload | Template | Notes |
|----------|----------|-------|
| `hybrid-rag-query` | `query.yaml` + `query-hpa.yaml` | Stateless MCP gateway; min 2 replicas |
| `hybrid-rag-ingest` orchestrator | `ingest.yaml` | Admin API `:8020` |
| Celery workers | `ingest.yaml` | Horizontally scaled |
| `mod-chat` | `mod-chat.yaml` | Optional BFF + static web |
| Ingress | `ingress.yaml` | SSE-friendly annotations (INF-P4) |
| CronJobs | `cronjobs.yaml` | E-22 version prune, E-44 session prune |

Bundled **infra stores** (Qdrant, Neo4j, Postgres, Redis, MinIO) are **not** in this sketch — use managed endpoints (`stores.mode: managed`) or install infra separately.

## Install

```bash
# Render locally (no cluster required)
helm template hybrid-rag ./deploy/helm/hybrid-rag -f deploy/helm/hybrid-rag/values-prod.yaml

# Install (requires secrets + managed store URLs)
helm upgrade --install hybrid-rag ./deploy/helm/hybrid-rag \
  -f deploy/helm/hybrid-rag/values-prod.yaml \
  --namespace hybrid-rag --create-namespace
```

## Secrets

Create out-of-band (External Secrets Operator recommended):

- `hybrid-rag-query-secrets` — `CATALOG_DSN_*`, `NEO4J_PASSWORD`, `MINIO_SECRET_KEY`, Langfuse keys
- `hybrid-rag-ingest-secrets` — `CATALOG_DSN`, store credentials, Celery secrets

## OQ1 — managed vs self-hosted

Set `stores.mode: managed` and override `stores.qdrant.url`, `stores.neo4j.uri`, `stores.postgres.host`, `stores.redis.url`, `stores.minio.endpoint` in `values-prod.yaml`.

Self-hosted dev parity remains `make bootstrap` + Compose.
