# Scale-Out Read Replicas (INF-P6)

**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md §12.4 · E-24 multi-region  
**Related:** [`docs/MULTI_REGION.md`](../../docs/MULTI_REGION.md)

Normative guidance for scaling **read-heavy** stores beyond single-node compose.

---

## Qdrant read replicas

| Signal | Action |
|--------|--------|
| Search QPS > 500/s per node | Add read replica in same region as query |
| Cross-region query | Regional replica + `QDRANT_URL` per query Deployment |

Writes remain on **leader** collection; ingest `QdrantWriter` targets leader DSN only.

**Regulated tier (E-33):** per-tenant physical collections still replicate with provider policy.

---

## Neo4j read replicas

| Signal | Action |
|--------|--------|
| Graph enrich CPU high | Enable read replica for Cypher read paths |
| Write load | Keep ingest on primary bolt URI |

Query `graph_enrich.py` SHOULD use `NEO4J_URI` read routing when `NEO4J_READ_URI` is set (future env).

---

## Postgres catalog

| Role | DSN | Consumer |
|------|-----|----------|
| Leader | `CATALOG_DSN` (ingest RW) | ingest, migrations |
| Read replica | `CATALOG_DSN_RO` | query catalog tools |

Lag SLO: **< 30s** p99 (`CATALOG_REPLICATION_LAG_SLO_SECONDS`).

---

## Operational checklist

1. Provision replica with same schema version (migrations `001`–`005`)
2. Point regional query at replica URL for `CATALOG_DSN_RO`
3. Monitor lag + `rag_ttft_ms` p95 per region
4. Fail back to primary catalog if lag exceeds SLO 5m

---

## Validation

Contract: `ingest/tests/contract/test_infra_scale_out.py`
