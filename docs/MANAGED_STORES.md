# Managed vs Self-Hosted Stores (OQ1)

**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md §12.6 · Helm `stores.mode`  
**Helm:** `deploy/helm/hybrid-rag/values.yaml` / `values-prod.yaml`

Enterprise deployments choose between **self-hosted** data plane (compose / on-prem K8s) and **managed** vendor endpoints.

---

## Decision matrix

| Store | Self-hosted | Managed | Backup owner |
|-------|-------------|---------|--------------|
| **Qdrant** | `infra/compose` | Qdrant Cloud | Vendor or `make backup` |
| **Neo4j** | compose | Aura / enterprise | Vendor |
| **Postgres catalog** | compose | RDS / Cloud SQL | PITR + `004_*` grants |
| **Redis** | compose | ElastiCache / Memorystore | Ephemeral OK for cache; broker persistence policy |
| **MinIO** | compose | S3 / GCS | Bucket replication |

**Rule:** `stores.mode: managed` in Helm **requires** all URLs in `values-prod.yaml` overlays — chart does not provision stores.

---

## Configuration

```yaml
stores:
  mode: managed   # selfHosted | managed
  qdrant:
    url: https://qdrant.example.com:6333
  postgres:
    host: catalog.example.com
```

Query + ingest ConfigMaps inherit store URLs; secrets hold credentials (`existingSecret`).

---

## Compatibility

See `docs/releases/compatibility.json` — `index_schema_version` and plane versions must match regardless of store mode.

---

## Validation

```bash
make validate-rag-v1
```
