# Multi-Region Read Path (E-24)

**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md §12.4  
**Resolves:** Future note at §12.4 — catalog replication lag SLO &lt; 30s

This document is the **normative expansion** for multi-region deployments where **query** serves read traffic close to users while **ingest** and vector writes remain on a primary region.

---

## 1. Architecture

```mermaid
flowchart LR
    subgraph primary [Primary region — us-east-1]
        ING[hybrid-rag-ingest]
        PGW[(Postgres catalog leader)]
        QDRW[(Qdrant leader)]
        N4J[(Neo4j)]
    end
    subgraph read [Read region — eu-west-1]
        Q1[hybrid-rag-query x N]
        PGR[(Postgres read replica)]
        QDRR[(Qdrant read replica)]
    end
    ING --> PGW
    ING --> QDRW
    ING --> N4J
    PGW -.->|async replication| PGR
    QDRW -.->|read replica| QDRR
    Q1 --> PGR
    Q1 --> QDRR
```

| Component | Primary | Read region | Write path |
|-----------|---------|-------------|------------|
| **Postgres catalog** | Leader | Read replica | Ingest only (`CATALOG_DSN_RW`) |
| **Qdrant** | Leader | Read replica (search) | Ingest batch writes |
| **Neo4j** | Single cluster / primary | Optional read replica (INF-P6) | Ingest graph upserts |
| **hybrid-rag-query** | Optional | **Deploy here** | Stateless — no writes |
| **hybrid-rag-ingest** | **Primary only** | Do not run workers | Celery beat = 1 |

---

## 2. SLOs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Catalog replication lag | **&lt; 30s** p99 | `pg_stat_replication.replay_lag` or managed-DB metric |
| Qdrant replica lag | **&lt; 60s** | Provider dashboard / custom probe |
| Query TTFT degradation vs single-region | **&lt; +15%** | `rag_ttft_ms` p95 per region |
| Stale read visibility | Acceptable for catalog ACL/collection metadata | Not for in-flight ingest jobs |

**Failover:** If replica lag exceeds SLO for 5m, route catalog reads to primary DSN (higher latency) via config flip — document in runbook.

---

## 3. Configuration

### 3.1 Query (read region)

Set in regional `hybrid-rag-query` deployment:

```bash
# Regional read replica for catalog metadata (query_ro role)
CATALOG_DSN_RO=postgresql://query_ro:***@catalog-replica.eu-west-1.example.com:5432/catalog

# Vector search — regional Qdrant read replica
QDRANT_URL=https://qdrant-replica.eu-west-1.example.com:6333

# Sessions/tokens stay on primary until E-32 federated MCP
CATALOG_DSN_SESSION=postgresql://query_session:***@catalog.us-east-1.example.com:5432/catalog
CATALOG_DSN_TOKEN=postgresql://query_token:***@catalog.us-east-1.example.com:5432/catalog
```

**Co-location:** Query pods SHOULD sit in the same AZ as regional Qdrant replica for &lt; 2ms RTT (§12.4).

### 3.2 Helm overlay

`deploy/helm/hybrid-rag/values-prod.yaml` includes a `multiRegion` block. Enable per release:

```yaml
multiRegion:
  enabled: true
  primaryRegion: us-east-1
  readRegions:
    - name: eu-west-1
      queryReplicaCount: 3
  catalogReplicationLagSloSeconds: 30
```

Regional installs use `-f values-prod.yaml -f values-eu-west-1.yaml` with overrides for `stores.qdrant.url` and secret-backed `CATALOG_DSN_RO`.

### 3.3 Ingest (primary only)

No change to write DSNs. Connector sync and Celery workers run **only** in the primary region to avoid split-brain schedules (ingest SPEC: beat replicas = 1).

---

## 4. Rollout checklist

1. Provision Postgres read replica + `query_ro` grants (migration `004_grant_query_roles_v1.sql`).
2. Enable Qdrant read replica; verify search parity on sample tenant.
3. Deploy query Deployment in read region with regional env + `warmup_clients()`.
4. Point regional ingress / Caddy at local query Service.
5. Monitor `catalog_replication_lag_seconds` and `rag_ttft_ms` dashboards (SigNoz E-23).
6. Run `query/benchmarks/load_test.py` from read region before cutover.

---

## 5. Anti-patterns

| Anti-pattern | Why |
|--------------|-----|
| Ingest workers in multiple regions | Duplicate connector schedules, conflicting writes |
| Scale query in read region without Qdrant replica | Cross-region search latency dominates TTFT |
| Use replica `CATALOG_DSN_RO` for session writes | `query_ro` is SELECT-only — sessions need `CATALOG_DSN_SESSION` on primary |

---

## 6. Future (E-32)

Federated MCP catalog routing is implemented — see [`docs/FEDERATED_MCP.md`](./FEDERATED_MCP.md). E-24 covers **read replica placement**; E-32 adds **cross-region catalog tool federation**.
