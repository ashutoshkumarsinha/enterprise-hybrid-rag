# Architect guide

**Audience:** Solution architects, security reviewers, and technical leads designing integrations and enterprise rollouts  
**Prerequisites:** Familiarity with RAG, vector search, and OIDC; read platform spec §3 and §3A first

---

## 1. Architectural intent

Enterprise Hybrid RAG is a **modular** platform: five replaceable runtime planes connected by explicit interfaces (IF-1 … IF-6). The **MCP server** is the primary integration surface; HTTP streaming complements TTFT-sensitive clients.

```mermaid
flowchart TB
    subgraph Clients
        CHAT[mod-chat BFF/UI]
        MCPHOST[MCP Hosts]
    end

    subgraph hybrid_rag_query["hybrid-rag-query"]
        MCP[MCP + HTTP gateway]
        LG[LangGraph pipeline]
    end

    subgraph hybrid_rag_ingest["hybrid-rag-ingest"]
        ORCH[Orchestrator]
        WRK[Celery workers]
    end

    subgraph hybrid_rag_infra["hybrid-rag-infra"]
        STORES[(Qdrant Neo4j Redis Postgres MinIO)]
        KC[Keycloak]
        EDGE[Caddy]
    end

    subgraph hybrid_rag_inference["hybrid-rag-inference"]
        VLLM[vLLM OpenAI API]
        RERANK[Reranker HTTP]
    end

    subgraph hybrid_rag_obs["hybrid-rag-observability"]
        LF[Langfuse]
        OTEL[OTel / Jaeger]
    end

    CHAT --> EDGE
    MCPHOST --> EDGE
    EDGE --> MCP
    MCP --> LG
    LG --> STORES
    LG --> VLLM
    LG --> RERANK
    ORCH --> WRK
    WRK --> STORES
    WRK --> VLLM
    LG --> LF
    LG --> OTEL
```

---

## 2. Interface catalog (IF-*)

| ID | From → To | Transport | Contract |
|----|-----------|-----------|----------|
| IF-1 | ingest → stores | gRPC/HTTP, SQL | Chunk payload, catalog DDL — [SHARED_CONTRACTS.md](../modules/SHARED_CONTRACTS.md) |
| IF-2 | query → stores | gRPC, Bolt, Redis | Read-only retrieval + cache |
| IF-3 | ingest/query → MinIO | S3 API | Presigned URLs, bucket policy — [MINIO.md](../infra/docs/MINIO.md) |
| IF-4 | query/ingest → inference | OpenAI-compatible HTTP | **No** vLLM import in app images |
| IF-5 | apps → observability | OTLP, Langfuse SDK | SDK only in app images |
| IF-6 | clients → query | MCP, SSE, OIDC JWT | Tenant binding, ACL — §9 |

```mermaid
flowchart LR
    subgraph IF4["IF-4 Inference boundary"]
        APP[query / ingest Python]
        HTTP[HTTP JSON OpenAI shape]
        VLLM[vLLM container]
    end
    APP -->|MUST NOT import torch/vLLM| HTTP --> VLLM
```

---

## 3. Data architecture

### 3.1 Entity model

| Entity | Store | Purpose |
|--------|-------|---------|
| Chunk vectors + payload | Qdrant | Hybrid retrieval |
| Document graph | Neo4j | Hierarchy, cross-refs, media links |
| Catalog metadata + ACL | Postgres | Source of truth for scope and permissions |
| Query cache | Redis | Result cache, rate limits |
| Raw / image assets | MinIO | Off-vector blobs |

### 3.2 Multi-tenancy

Logical isolation by `tenant_id` on **every** Qdrant filter and catalog query (FR-02). Cross-tenant retrieval must be impossible at the API layer.

---

## 4. Query path (logical)

```mermaid
sequenceDiagram
    participant Client
    participant Query as hybrid-rag-query
    participant Cache as Redis
    participant Inf as inference
    participant QD as Qdrant
    participant LLM as vLLM chat

    Client->>Query: research_documents / stream
    Query->>Cache: check cache
    alt cache hit
        Query-->>Client: cached answer
    else cache miss
        Query->>Inf: embed query
        Query->>QD: hybrid retrieve + tenant filter
        Query->>Inf: rerank
        Query->>LLM: grounded answer stream
        Query-->>Client: tokens + sources + telemetry
    end
```

**Degradation ladder** (§6.3.2): under load, shed optional stages (graph enrich, rerank, supervisor) before returning 503.

---

## 5. Ingest path (logical)

```mermaid
flowchart LR
    SRC[Sources] --> PARSE[Parse PyMuPDF / Docling]
    PARSE --> CHUNK[Chunk + metadata]
    CHUNK --> EMB[Embed via IF-4]
    EMB --> WRITE[Write Qdrant + catalog + MinIO]
    WRITE --> EVT[ingest.completed event]
    EVT --> CACHE[Invalidate query cache]
```

**Idempotency key:** `(tenant_id, collection_id, document_id, content_hash)`.

---

## 6. Security architecture

```mermaid
sequenceDiagram
    participant Browser
    participant KC as Keycloak
    participant BFF as mod-chat BFF
    participant Query as hybrid-rag-query

    Browser->>KC: OIDC PKCE login
    KC-->>Browser: JWT
    Browser->>BFF: Session + JWT
    BFF->>Query: Bearer JWT + traceparent + tenant_id
    Query->>Query: Validate JWT + ACL + rate limits
```

| Layer | Control |
|-------|---------|
| Edge | TLS, optional static bearer on MCP SSE (dev/S2S only) |
| Application | OIDC JWT when `auth.required=true` |
| Data | Tenant filter + ACL empty-set semantics |
| Audit | Structured logs; Langfuse sessions |

---

## 7. Observability architecture

| Signal | Tool | Consumer |
|--------|------|----------|
| LLM cost, sessions, scores | Langfuse | Product + ops |
| Distributed traces | OTel → Jaeger (default) / SigNoz (optional §10.5) | Engineering |
| APM SLO dashboards | SigNoz when `PROFILE=signoz` — [observability/docs/SIGNOZ.md](../observability/docs/SIGNOZ.md) | SRE |
| Metrics | Prometheus (`PROFILE=metrics`) + SigNoz histograms §10.5.3 | SLO dashboards |

LangGraph nodes emit per-stage `timings_ms` (FR-09). Ragas gates quality on release; LangSmith optional in CI (TL-07).

---

## 8. Scaling patterns

| Pattern | When |
|---------|------|
| Horizontal query replicas | Read-heavy; stateless except Redis cache |
| Ingest worker pool | Corpus onboarding bursts |
| Qdrant sharding | >10M chunks per tenant (future) |
| Separate inference pool | Embed vs chat SLA conflict |

Connection pool defaults: spec §18.16. Circuit breakers: §18.15.

---

## 9. Architecture decisions (index)

Full ADR list: platform spec §17. Highlights:

| ID | Decision |
|----|----------|
| OD1 | MCP-first API |
| OD4 | LangGraph for query orchestration |
| OD5 | Static bearer config-driven — not sole prod auth |
| OD9 | User-level ACL requires OIDC JWT |

---

## 10. Extension points

| Extension | Interface |
|-----------|-----------|
| Connectors v2 | §5.8 — S3 first |
| Admin ACL API | E-16 in roadmap |
| mod-chat | Optional BFF — no direct store access (TL-03) |
| Helm / K8s | E-19 — `deploy/helm/` planned |

---

## 11. Related documentation

| Document | Purpose |
|----------|---------|
| [ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md) §1.4 | **Implementation inventory** — stub vs shipped |
| [ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md) | Normative platform spec |
| [SHARED_CONTRACTS.md](../modules/SHARED_CONTRACTS.md) | Cross-plane schemas |
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | Operational bootstrap |
| [DOCUMENTATION.md](./DOCUMENTATION.md) | Doc and diagram standards |
| [SPEC_ROADMAP.md](./SPEC_ROADMAP.md) | Planned depth |
