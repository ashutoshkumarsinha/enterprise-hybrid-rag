# Deployment guide

**Audience:** DevOps, SRE, and platform engineers who bootstrap, upgrade, and operate Hybrid RAG stacks  
**Prerequisites:** Docker Compose (dev), optional GPU host, access to secrets store in production

---

## 1. Deployment overview

The platform splits into **five runtime sub-projects** plus shared contracts. You can run everything on a laptop or split planes across nodes.

```mermaid
flowchart TB
    subgraph infra["hybrid-rag-infra"]
        QD[(Qdrant)]
        NEO[(Neo4j)]
        PG[(Postgres)]
        RD[(Redis)]
        MINIO[(MinIO)]
        KC[Keycloak]
        CADDY[Caddy edge]
    end

    subgraph apps["Application planes"]
        ING[hybrid-rag-ingest :8020]
        QRY[hybrid-rag-query :8010]
        INF[hybrid-rag-inference]
    end

    subgraph obs["hybrid-rag-observability"]
        LF[Langfuse]
        OTEL[OTel collector]
        JAE[Jaeger]
        SZ[SigNoz optional]
    end

    ING --> infra
    QRY --> infra
    QRY --> INF
    ING --> INF
    QRY --> obs
    CADDY --> QRY
```

**Canonical bootstrap:** platform spec §12.5. This guide summarizes practical steps.

---

## 2. Topology choices

| Topology | Modules | Use case |
|----------|---------|----------|
| **Laptop dev** | All-in-one Compose on localhost | Developer workstation |
| **Split prod** | Query ×N, ingest ×M, managed stores | Enterprise default |
| **Query-only scale** | HPA on query; ingest batch nightly | Read-heavy |
| **Ingest burst** | Temporary ingest workers | Large corpus onboarding |
| **Observability optional** | Langfuse Cloud + collector only | Reduce self-hosted ops |
| **Auth optional (dev)** | Keycloak skipped | Local pipeline testing only — **never production** |

```mermaid
flowchart TB
    subgraph split_prod["Split production (recommended)"]
        INFRA_NODE[Infra node: stores + edge]
        QUERY_NODES[Query replicas N]
        INGEST_NODES[Ingest workers M]
        GPU_NODE[Inference GPU pool]
    end

    INFRA_NODE --> QUERY_NODES
    INFRA_NODE --> INGEST_NODES
    QUERY_NODES --> GPU_NODE
    INGEST_NODES --> GPU_NODE
```

---

## 3. Bootstrap order (dev)

Bring up dependencies before application planes.

```mermaid
flowchart LR
    A[1. infra stores] --> B[2. inference]
    B --> C[3. observability]
    C --> D[4. ingest]
    D --> E[5. query]
    E --> F[6. health gates]
```

### 3.1 Infrastructure

```bash
# From repo root (recommended)
make env
make bootstrap INFERENCE_PROFILE=gpu_24gb
make health
```

Or manually per plane:

```bash
cd infra
cp .env.example .env
# Edit passwords, MinIO keys, Keycloak admin
docker compose up -d
./scripts/init-minio.sh   # buckets + IAM
./scripts/init-db.sh      # when available — catalog schema
make health
```

### 3.2 Inference

```bash
cd inference
cp .env.example .env
# Set profile: lima_12gb | gpu_24gb | etc.
docker compose --profile gpu up -d
make health
```

### 3.3 Observability

**Default** (Langfuse + Jaeger):

```bash
cd observability
cp .env.example .env
make up
make health
```

**SigNoz profile** (collector fan-out to `signoz-otel-collector` — platform §10.5):

```bash
cd observability
cp .env.example .env
make up PROFILE=signoz
make health
make synthetic-trace   # verify trace in Jaeger; SigNoz when full UI stack deployed
```

See [observability/docs/SIGNOZ.md](../observability/docs/SIGNOZ.md). GPU enterprise prod often enables SigNoz for TTFT and ingest SLO dashboards.

### 3.4 Ingest

```bash
cd ingest
cp .env.example .env
docker compose up -d
make health
```

### 3.5 Query

```bash
cd query
cp .env.example .env
docker compose up -d
make health
```

Each sub-project README documents ports and `make` targets.

### 3.6 Catalog migrations

After infra Postgres is healthy, apply catalog DDL (platform §4.4, §12.5 step 3):

```bash
# Recommended (when migrate.py lands):
cd ingest && make migrate

# Manual equivalent:
export CATALOG_DSN="postgresql://ingest_rw:${INGEST_RW_PASSWORD}@127.0.0.1:5432/catalog"
for f in migrations/00{1,2,3,4}_*.sql; do
  psql "$CATALOG_DSN" -v ON_ERROR_STOP=1 -f "$f"
done
```

| Migration | Purpose |
|-----------|---------|
| `001_catalog_v1.sql` | Core catalog tables |
| `002_conversation_sessions_v1.sql` | MCP conversation sessions |
| `003_mcp_access_tokens_v1.sql` | `rag_mcp_*` token RBAC |
| `004_grant_query_roles_v1.sql` | Grants for `query_session_rw`, `query_token_rw` |

See [ingest/docs/MIGRATIONS.md](../ingest/docs/MIGRATIONS.md). Mint first MCP admin token per [query/docs/TOKEN_ADMIN.md](../query/docs/TOKEN_ADMIN.md) before enabling `auth.required=true`.

---

## 4. Configuration profiles

Shared values **must match** across modules: `embed_dimension`, `qdrant_collection`, `index_schema_version`, OTLP endpoint, OIDC issuer.

| Profile | GPU | Typical use |
|---------|-----|-------------|
| `lima_12gb` | CPU / small GPU | Laptop dev |
| `gpu_24gb` | 24 GB VRAM | Single-node prod |
| `gpu_cluster` | Multi-GPU | High throughput |

Performance tuning: [PERFORMANCE.md](./PERFORMANCE.md) and per-plane `docs/PERFORMANCE.md`.

---

## 5. Health gates

`/healthz` on query returns **503** when research path is degraded (FR-06).

```mermaid
flowchart TB
    HZ["GET /healthz"] --> INF_OK{Inference up?}
    INF_OK -->|no| DEG[503 degraded]
    INF_OK -->|yes| QD_OK{Qdrant + catalog?}
    QD_OK -->|no| DEG
    QD_OK -->|yes| OK[200 research_ready]
```

**Release gate checklist:**

- [ ] All sub-project `make health` green
- [ ] `pytest tests/unit tests/contract` (per app repo)
- [ ] Nightly: integration + Ragas + baselines (see [TESTING.md](./TESTING.md))
- [ ] Pre-release: k6/Locust soak (FR-32)

---

## 6. Secrets and TLS

| Secret | Location |
|--------|----------|
| MinIO access keys | `infra/.env` → app `.env` |
| Postgres DSNs | Separate RO user for query |
| Keycloak client secrets | `infra` + mod-chat BFF |
| Caddy MCP bearer (dev) | `infra/caddy/` — not sufficient alone for user ACL |

Production: TLS at Caddy or upstream LB; `auth.required=true` on query.

---

## 7. Upgrades and releases

Sub-projects version independently with compatibility matrix (spec §12.6):

See **[RELEASE_MATRIX.md](./RELEASE_MATRIX.md)** for the full cross-plane matrix and release gates.

1. Upgrade **infra** stores (backup first)
2. Upgrade **inference** (model URLs unchanged if possible)
3. Rolling restart **query** replicas
4. Drain and upgrade **ingest** workers

Tag platform releases `rag-v*` only after release gates pass.

---

## 8. Capacity planning

| Resource | Driver |
|----------|--------|
| Qdrant disk | Chunk count × (vector + payload) |
| MinIO | Raw assets + diagram extracts |
| GPU VRAM | vLLM model + concurrent streams |
| Postgres | Catalog rows + ACL + job history |

See platform spec §12.8 and [PERFORMANCE.md](./PERFORMANCE.md) §capacity.

---

## 9. Troubleshooting

| Symptom | Check | Fix |
|---------|-------|-----|
| 503 on `/healthz` | Inference URL, Qdrant, catalog DSN | Fix dependency; see query logs |
| Embed failures | vLLM OOM | Lower concurrency; smaller model profile |
| Slow queries | Cache off, wide scope | Enable cache; tune `search_ef` |
| Ingest never completes | Celery broker, Redis | Verify worker containers |
| Traces missing | OTLP endpoint | observability collector routing |

---

## 10. Related documentation

| Document | Purpose |
|----------|---------|
| [ADMIN_GUIDE.md](./ADMIN_GUIDE.md) | Post-deploy content operations |
| [ARCHITECT_GUIDE.md](./ARCHITECT_GUIDE.md) | Interface boundaries |
| [infra/README.md](../infra/README.md) | Infra quick start |
| [infra/docs/MINIO.md](../infra/docs/MINIO.md) | Object storage |
| [ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md) §11–12 | Normative deploy spec |
