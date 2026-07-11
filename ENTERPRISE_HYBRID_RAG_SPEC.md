# Enterprise Hybrid RAG — Product Specification

**Status:** Draft v0.28 (v0.28 implementation bundle)  
**Audience:** Platform engineers, solution architects, security reviewers  
**Scope:** Document-agnostic ingestion, hybrid retrieval, graph enrichment, MCP-first API, enterprise chat UI  
**Changelog:** v0.28 — query auth (`auth.py`, `jwt_auth.py`, `token_store.py`, `session_store.py`), MCP HTTP + stdio handlers, LG-1–LG-4 clients/benchmarks, LG-2/LG-3 streaming + cache, contract tests; v0.27 — §22 roadmap sync, token admin OpenAPI (§7.13.10), migration runner (§4.4.4), Postgres query roles + `004_*` grants, remaining MCP JSON schemas; v0.26 — **token-based MCP RBAC** — `rag_mcp_*` Bearer tokens (§7.13), `mcp_access_tokens` DDL, FR-23/45/47–48; v0.25 — RBAC permission matrix; v0.24 — sessions §7.11; v0.23 — SigNoz §10.5; v0.22 — catalog DDL, IF-6

> **Note:** This document is the **platform overview**. Module-specific normative specs live in [`modules/`](./modules/) and sub-project `SPEC.md` files. The **enhancement roadmap** is in [`docs/SPEC_ROADMAP.md`](./docs/SPEC_ROADMAP.md). **Performance tuning** is in [`docs/PERFORMANCE.md`](./docs/PERFORMANCE.md). **Testing & TDD** is in [`docs/TESTING.md`](./docs/TESTING.md). **Documentation standards** are in [`docs/DOCUMENTATION.md`](./docs/DOCUMENTATION.md). **Coding standards** are in [`docs/CODING_STANDARDS.md`](./docs/CODING_STANDARDS.md) §23. **What to spec next** is in §22. **What exists on disk today** is in §1.4.

---

## 1. Executive summary

This specification defines an **enterprise-grade Hybrid RAG platform** that ingests **any product or generic document corpus** (PDF, DOCX, HTML, Markdown, plain text, structured data exports, images/diagrams) and answers natural-language questions **grounded in ingested content only**.

| Reference pattern | Enterprise generalization |
|-------------------|---------------------------|
| Domain-specific `.docx` + folder tree | Arbitrary layouts + manifest-driven metadata |
| `spec` / `release` scope model | `collection` / `document` / `version` / `product` metadata |
| Domain-specific research MCP tool | `research_documents` (domain-neutral) |
| Domain catalog tool | `list_indexed_documents` |
| Domain graph viz tool | `visualize_document_graph` |
| Qdrant + Neo4j + Redis + MinIO | Same store topology; tenant-aware naming |
| Celery batch ingest | Same; plus connector framework (S3, filesystem) |
| Langfuse + OTel/Jaeger | Unified observability stack in `observability/` sub-project |
| React BFF + Keycloak + MCP multiplexer | Same; RBAC extended to collections |

**Design principle:** Keep the **retrieval engine generic**; push domain semantics into **metadata schema**, **ingest connectors**, and **prompt templates**—not into core pipeline code.

**TDD principle:** **Tests and frozen contracts precede implementation** at module boundaries. Red → green → refactor; contract tests block every PR (§13.4, §19, [docs/TESTING.md](./docs/TESTING.md)).

**Documentation principle:** **Every audience has a maintained guide** — end users, administrators, deployment engineers, architects, and developers. Architecture and flow diagrams use **Mermaid**; public code uses **novice-readable** docstrings (§21, [docs/DOCUMENTATION.md](./docs/DOCUMENTATION.md)).

**Coding principle:** Application code follows **[docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md)** — typed Python, Black/Ruff formatting, boundary-safe clients, structured logging, and LangGraph patterns (§23, G15).

**Modularity principle:** **Query**, **Ingestion**, **Infrastructure**, **Inference**, and **Observability** MUST each be deployable and replaceable independently. Cross-module coupling is limited to **shared contracts** (index schema, catalog API, domain events, OTLP/Langfuse hooks)—never shared code imports across sub-project boundaries.

### 1.1 Module map

| Module | ID | Deploy unit | Spec |
|--------|-----|-------------|------|
| **Query & MCP** | `hybrid-rag-query` | MCP + HTTP gateway + RAG pipeline — **separate sub-project** | [`query/`](./query/) |
| **Ingestion** | `hybrid-rag-ingest` | Orchestrator + Celery workers — **separate sub-project** | [`ingest/`](./ingest/) |
| **Infrastructure** | `hybrid-rag-infra` | Qdrant, Neo4j, Redis, MinIO, Postgres, Keycloak, Caddy — **separate sub-project** | [`infra/`](./infra/) |
| **Inference** | `hybrid-rag-inference` | vLLM chat, embed, vision, reranker, smoke LLM — **separate sub-project** | [`inference/`](./inference/) |
| **Observability** | `hybrid-rag-observability` | Langfuse + OTel collector + Jaeger (+ optional SigNoz) — **separate sub-project** | [`observability/`](./observability/) |
| **Shared contracts** | `mod-kernel` | Schemas + event types only (no runtime) | [`modules/SHARED_CONTRACTS.md`](./modules/SHARED_CONTRACTS.md) |

### 1.2 Stack components (deep specs)

| Component | Role | Host | Spec |
|-----------|------|------|------|
| **Stores** | Qdrant, Neo4j, Redis, MinIO, Postgres | infra sub-project | [`infra/`](./infra/) |
| **vLLM + rerankers** | OpenAI-compatible LLM, embed, vision, reranker sidecars, smoke LLM | inference sub-project | [`inference/`](./inference/) |
| **Langfuse** | LLM traces, token cost, sessions | **observability** sub-project (`langfuse` service) | [`observability/docs/LANGFUSE.md`](./observability/docs/LANGFUSE.md) |
| **OTel / Jaeger** | HTTP/ingest distributed traces | **observability** sub-project | [`observability/docs/OTEL.md`](./observability/docs/OTEL.md) |
| **Keycloak** | OIDC identity, realm RBAC | **infra** sub-project | [`infra/docs/KEYCLOAK.md`](./infra/docs/KEYCLOAK.md) |
| **Caddy** | TLS + MCP SSE reverse proxy | infra sub-project | [`infra/docs/CADDY.md`](./infra/docs/CADDY.md) |
| **SigNoz** | HTTP/APM traces (complements Langfuse) | obs sub-project | [`observability/docs/SIGNOZ.md`](./observability/docs/SIGNOZ.md) |

**Out of scope for core sub-projects** (optional client): Chat UI + BFF (`mod-chat`) — consumes `hybrid-rag-query` only via MCP/HTTP; never touches stores directly.

### 1.3 Implementation technology stack

The platform is **polyglot by design**. Language choice follows sub-project boundaries — not a single runtime for everything.

#### Normative language map

| Sub-project / component | Language | Runtime | Rationale |
|-------------------------|----------|---------|-----------|
| **hybrid-rag-query** | **Python 3.12+** | FastAPI + uvicorn | **LangGraph** pipeline, MCP SDK, LangSmith tracing, Langfuse/OTel |
| **hybrid-rag-ingest** | **Python 3.12+** | FastAPI + Celery | Document parsers (**PyMuPDF** fast path, **Docling** quality tier), batch embed |
| **hybrid-rag-inference** (reranker sidecar) | **Python 3.12+** | FastAPI / uvicorn | `sentence-transformers` CrossEncoder; HTTP `POST /predict` |
| **mod-chat** BFF (optional) | **TypeScript** | Node 20+ (Express/Fastify) | OIDC sessions, MCP multiplexer, React adjacency |
| **mod-chat** UI (optional) | **TypeScript** | React + Vite | SSE chat, scope bar, catalog panels |
| **hybrid-rag-infra** | Compose + config | Qdrant, Neo4j, Redis, MinIO, Postgres, Keycloak, Caddy | No custom app server — tuned upstream images |
| **hybrid-rag-observability** | Compose + YAML | Langfuse, OTel collector, Jaeger | SDK-only in application images |
| **hybrid-rag-inference** (vLLM) | — | vLLM OpenAI server (Python/CUDA upstream) | Apps use **HTTP only** — no vLLM import in query/ingest (IF-4) |
| **mod-kernel** | Schema definitions | JSON Schema / TOML contracts | No runtime |

#### Performance principle (language)

Application language is **not** the primary latency bottleneck. Typical GPU query breakdown:

| Stage | Share of wall time |
|-------|-------------------|
| LLM answer + TTFT | 60–85% |
| Rerank (cross-encoder) | 10–25% |
| Embed + Qdrant retrieve | 5–15% |
| Python gateway overhead | < 2% |

**Rule:** Keep Python **thin** — pooled HTTP clients to inference, no model weights in query/ingest images. Optimize via [`docs/PERFORMANCE.md`](./docs/PERFORMANCE.md), [`infra/docs/PERFORMANCE.md`](./infra/docs/PERFORMANCE.md), and GPU/store tuning — not by rewriting the MCP gateway in Rust for v1.

#### Application constraints

| ID | Constraint |
|----|------------|
| TL-01 | `hybrid-rag-query` and `hybrid-rag-ingest` **SHOULD** use Python **3.12+** |
| TL-02 | Query/ingest images **MUST NOT** import vLLM, torch, or load LLM weights (IF-4) |
| TL-03 | `mod-chat` **SHOULD** use TypeScript; **MUST NOT** connect to Qdrant/Neo4j directly |
| TL-04 | Store server code **MUST NOT** ship inside query/ingest images |
| TL-05 | Observability servers **MUST NOT** ship inside application images (SDK only, IF-5) |
| TL-06 | RAG pipeline in `hybrid-rag-query` **MUST** be orchestrated with **LangGraph** (`app/rag_graph.py`) |
| TL-07 | LangSmith tracing **SHOULD** be enabled in non-prod and eval CI; optional in prod via `LANGCHAIN_TRACING_V2` |
| TL-08 | RAG **quality** evaluation gates (faithfulness, relevancy, context recall) **MUST** use **[Ragas](https://docs.ragas.io/)** — see §13.2 |
| TL-09 | Load and soak tests **MUST** use **[k6](https://k6.io/)** (primary) or **[Locust](https://locust.io/)** (Python-native alternative) — see §13.1 |
| TL-10 | Complex PDF / Office layouts **SHOULD** route to **[Docling](https://github.com/docling-project/docling)** when `parser_profile = docling` or manifest `parser: docling` — see §5.1.1 |
| TL-11 | Sub-project development **SHOULD** follow **test-driven development** — failing contract or unit test before feature code at kernel/MCP/pipeline boundaries — see §19 |
| TL-12 | Architecture, sequence, state, and flow diagrams in normative docs **MUST** use **Mermaid** — no ASCII box diagrams; see §21.2 |
| TL-13 | Public Python functions/classes and TypeScript exports **MUST** have novice-readable docstrings (Google-style / TSDoc) per [docs/DOCUMENTATION.md](./docs/DOCUMENTATION.md) §4 and §23.3 |
| TL-14 | Python application sub-projects **MUST** use **Black** (line length 100) and **Ruff** lint; `make lint` or CI equivalent **SHOULD** block PRs — see §23.8 |
| TL-15 | Public Python functions and methods **MUST** include type hints (`from __future__ import annotations` in new modules) — see §23.4 |
| TL-16 | Query and ingest **SHOULD** emit structured logs with `tenant_id` and `request_id` (when present) on pipeline and HTTP paths — see §23.10 |

#### When to reconsider (future)

| Language | Consider only if… | Default for v1 |
|----------|-------------------|----------------|
| **Rust** | MCP gateway > 10k RPS, strict memory caps | Python FastAPI |
| **Go** | Custom ultra-light edge proxy replacing Caddy | Caddy in infra |
| **Java** | Enterprise mandate for JVM-only app tier | Python |

Cross-language coupling remains **HTTP + shared contracts** (§3.3, §4) — never shared code imports across sub-projects (FR-20).

### 1.4 Implementation inventory (repository reality)

> **Phase:** **rag-v1.0 release train** — P0–P3 roadmap complete; contract gates green via `make validate-rag-v1`. Live-stack cutover (health, migrate, Ragas, soak) remains operator checklist §4 in `docs/SPEC_ROADMAP.md`.

```mermaid
flowchart LR
    subgraph shipped["Shipped on disk"]
        QUERY[query LangGraph + MCP + federation + mTLS]
        INGEST[ingest parsers + connectors + quotas]
        INFRA[infra stores + Caddy mTLS + migrations 001–005]
        OBS[observability OTel + SigNoz + alerts]
        DEPLOY[chat-ui + helm + validate-rag-v1 gate]
    end

    subgraph live["Operator / live stack"]
        HEALTH[make health + migrate]
        PERF[Ragas + k6 soak]
        PROD[prod secrets + quotas]
    end

    shipped --> live
```

#### Sub-project status

| Sub-project | Docs | Compose / ops | Application code | Tests / schemas |
|-------------|------|---------------|------------------|-----------------|
| **query** | **Complete** | `compose/`, `Makefile`, `Dockerfile` | **rag-v1.0** — LangGraph, federation, mTLS listener, breakers | **130+ unit/contract tests** |
| **ingest** | **Complete** | `compose/`, worker `Dockerfile` | **v0.49+** — parsers, connectors (S3/filesystem), quotas, OTel | **175+ unit/contract tests**; migrations **001–005** |
| **infra** | **Complete** | Full store compose; Qdrant gRPC **6334** | `init-db.sh`, `postgres-init.sh`, Caddy mTLS render, Keycloak realm | Contract tests + `make health` |
| **inference** | **Complete** | vLLM compose profiles | `reranker/sidecar.py`; upstream vLLM images | Smoke + benchmark hooks |
| **observability** | **Complete** | Dev + prod collector, Jaeger, SigNoz | FR-40 metrics query+ingest; dashboards + Prometheus rules | Contract tests |
| **mod-kernel** | **Normative** | N/A | **11 JSON schemas** + `SHARED_CONTRACTS.md` | Cross-plane contract suite |

#### Key files on disk (reference)

| Path | Status | Notes |
|------|--------|-------|
| `query/app/clients/neo4j.py` | Implemented | Graph enrich + Mermaid document viz |
| `query/app/catalog_store.py` | Implemented | Postgres RO + in-memory; ACL-filtered catalog reads |
| `query/app/catalog_handlers.py` | Implemented | MCP catalog + graph viz tools |
| `query/app/graph_enrich.py` | Implemented | §6.13.2 context block formatting |
| `query/app/supervisor.py` | Implemented | Query rewrite + scope inference JSON (§6.7) |
| `query/app/rag_graph.py` | Implemented | Full LangGraph path + degrade ladder |
| `query/app/event_subscriber.py`, `acl_cache.py` | Implemented v0.39–0.42 | `rag:events` subscriber; ACL cache wired in `catalog_store._load_acl` |
| `query/app/mcp_server.py` | Implemented | `/healthz`, `/sse`, MCP tools, sessions, token admin |
| `query/app/mcp_stdio.py` | Implemented | stdio MCP transport (`python -m app.mcp_stdio`) |
| `query/app/jwt_auth.py` | Implemented | JWKS validation + `JWT_STUB` dev mode |
| `query/app/auth.py`, `token_store.py`, `session_store.py` | Implemented | MCP tokens + JWT bridge + tenant binding |
| `query/benchmarks/benchmark_rag.py` | Implemented v0.47 | §13.2.1 CLI + `--ragas` + `--compare-otel` (OBS-P3) |
| `query/benchmarks/load_test.py` | Implemented v0.48 | http + k6 + Locust soak wrapper (§13.1, NFR-23) |
| `.github/workflows/ci.yml`, `nightly.yml` | Implemented v0.43 | PR + nightly CI per §19.6 |
| `ingest/app/migrate.py` | Implemented | Migration runner §4.4.4 |
| `ingest/app/parsers/` | Implemented v0.32 | Router + text/md/html/json/csv/yaml/pdf/docx/docling (stub tier) |
| `ingest/app/pipeline.py`, `chunk_builder.py` | Implemented v0.32 | File → `chunk_payload.v1` |
| `ingest/app/orchestrator.py` | Implemented v0.40 | Admin ingest + connector sync + job poll (`0.7.0-beat`) |
| `ingest/app/writers.py`, `clients/embed.py`, `clients/qdrant.py`, `clients/neo4j.py` | Implemented v0.33 | Batch embed + Qdrant upsert + Neo4j merge (stub tier) |
| `ingest/app/acl_store.py`, `acl_handlers.py` | Implemented v0.34 | ACL grant CRUD + collection `default_acl` admin |
| `ingest/app/connectors/`, `connector_sync.py` | Implemented v0.35 | S3/MinIO + filesystem connector sync |
| `ingest/app/quota_store.py`, `quota_handlers.py` | Implemented v0.49 | FR-30 chunk quota at enqueue + admin GET/PUT quotas |
| `ingest/app/backpressure.py` | Implemented v0.46 | FR-29 Celery queue depth warn + enqueue pause (503) |
| `ingest/app/job_store.py`, `celery_results.py` | Implemented v0.45 | Job poll + Celery result backend reconcile |
| `ingest/app/beat_config.py`, `connector_enqueue.py` | Implemented v0.40 | Celery beat schedule + shared connector enqueue |
| `ingest/app/catalog_store.py` | Implemented v0.41 | Postgres/in-memory `documents` + `document_versions` on write |
| `ingest/benchmarks/benchmark_ingest.py` | Implemented v0.44 | Mock + live throughput gates (§13.1) |

#### Not yet on disk (operator / live only)

| Artifact | Notes |
|----------|-------|
| Production secrets + tenant quotas | Out-of-band Helm / vault |
| Live Ragas + k6 soak gates | `RAGAS_GATE=1` / `LOAD_GATE=1` |
| Managed store endpoints | `docs/MANAGED_STORES.md` — customer-specific URLs |

`chat-ui/` and `deploy/helm/` **are on disk** (E-18, E-19).

### 1.5 Stub-phase conventions (pre–rag-v1.0)

Until release train `rag-v1.0`, stub services **MUST** be identifiable in responses and docs:

| Convention | Rule |
|------------|------|
| **Version strings** | App `version` fields MAY include `-stub` or `-langgraph` suffix (e.g. `0.2.0-langgraph`); release tags use `query-v1.0.0` pattern (§12.6) — do not conflate |
| **Health checks** | Stub `/healthz` MAY return `research_ready: true` with all `checks.*_ok: true` **only when** `STUB_HEALTH=true` (dev default); production **MUST** probe live deps (FR-06) |
| **Response bodies** | Stub pipeline responses **SHOULD** include `"stub": true` (already in `rag_graph` abstain/answer paths) |
| **MCP server identity** | `query/docs/MCP.md` `version: 1.0.0` is **protocol contract version**; FastAPI app version is **build version** — both documented in §7.2 |
| **Admin routes** | Ingest `POST /admin/ingest/document` returns `"stub": false`; collection/job status still stub |
| **Code comments** | `# Stub:` or docstring **Stub:** naming replacement module (TL-13) |

**Migration:** When LG-1–LG-3 land, remove optimistic health defaults and enforce 503 on degraded path before `rag-v1.0` tag.

---

## 2. Goals and non-goals

### 2.1 Goals

| ID | Goal |
|----|------|
| G1 | Ingest heterogeneous document formats at scale (millions of chunks) with idempotent, resumable jobs |
| G2 | Hybrid retrieval: dense embeddings + sparse lexical (BM25-style) fused with RRF |
| G3 | Optional knowledge graph: document hierarchy, cross-references, media assets |
| G4 | **MCP server** as the primary integration surface for AI assistants and chat products — including **persistent conversation sessions** (§7.11) |
| G5 | HTTP companion routes for **token streaming** (low TTFT) and **health probes** |
| G6 | Multi-tenant ready: logical isolation by `tenant_id` + `collection_id` |
| G7 | Enterprise security: OIDC auth, secrets management, audit logs, data residency hooks |
| G8 | Observable end-to-end: Langfuse (LLM/cost/sessions) + OTel/Jaeger (distributed traces); optional SigNoz APM (§10.5) for SLO dashboards and alerts |
| G9 | Quality gates: golden sets, Ragas metrics, regression baselines, abstention on low confidence |
| G10 | Deployable from laptop → single-node prod → GPU cluster (**vLLM** default; Ollama for dev) |
| G11 | **Performance-first:** measurable latency budgets per pipeline stage; regression gates block deploys on p95 regressions |
| G12 | **Modular deploy:** Query, Ingest, Infra, Inference, and Observability each independently replaceable |
| G13 | **Test-driven delivery:** contract tests, frozen fixtures, and benchmark gates precede and block merges — §13.4, §19 |
| G14 | **Exhaustive documentation:** maintained guides for end users, admins, deployment, architects, and developers; Mermaid diagrams; novice-friendly code comments — §21 |
| G15 | **Consistent coding standards:** typed, formatted, boundary-safe application code per [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) — §23 |

**Performance principle:** Optimize the **critical path** (embed → retrieve → rerank → stream) before adding features. Every stage MUST be skippable, cacheable, or parallelizable when scope is explicit.

### 2.2 Non-goals (v1)

- Fine-tuning or training custom embedding models in-platform
- Real-time collaborative document editing
- Replacing enterprise search appliances (Solr/Elastic) for keyword-only search
- Guaranteed legal/compliance certification (SOC2/HIPAA) — architecture supports controls; certification is operational
- Automatic PII redaction at ingest (hook points defined; implementation optional)

### 2.3 Functional requirements

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-01 | Ingest MUST be idempotent per `(tenant_id, collection_id, document_id, content_hash)` | Re-running ingest does not duplicate Qdrant points |
| FR-02 | Query MUST enforce `tenant_id` on every Qdrant filter | Cross-tenant retrieval is impossible at API layer |
| FR-03 | ACL MUST be enforced at catalog lookup and Qdrant filter | Unauthorized principal receives empty results, not errors leaking titles |
| FR-04 | `research_documents` MUST return answer + **Sources** + telemetry footer in stable markdown | BFF parser contract tests pass against frozen fixtures |
| FR-05 | `POST /research/stream` MUST emit only `token`, `sources`, `telemetry`, `done`, `error` events | Contract test validates SSE JSON shape |
| FR-06 | `/healthz` MUST report `research_ready` only when inference + Qdrant + catalog are reachable | Returns HTTP 503 when degraded |
| FR-07 | Scope resolution MUST support explicit pins, query inference, and `require_explicit` mode | Golden-set scope accuracy ≥ configured gate |
| FR-08 | Abstention MUST skip LLM generation when `top_rerank_score < min_rerank_score` | Response includes `abstained: true` |
| FR-09 | Every query MUST emit per-stage `timings_ms` for all executed stages | Structured `rag_stage_ms` log line or telemetry footer |
| FR-10 | Ingest jobs MUST be resumable after worker crash | Job status transitions: `pending` → `running` → `completed` \| `failed` |
| FR-11 | Version ingest MUST be immutable | New `version_id` never overwrites prior Qdrant points in place |
| FR-12 | Connectors MUST record `source_uri`, `source_system`, and content hash in catalog | Incremental sync detects change by hash |
| FR-13 | Query path MUST use **one embed call** per request (dense + sparse from same pass) | No duplicate embed for scope + retrieve |
| FR-14 | MCP gateway MUST call `warmup_clients()` at startup | Qdrant, Neo4j, inference, reranker preloaded |
| FR-15 | Ingest MUST batch-embed (`embed(input=[...])`) when provider supports it | Reduces inference round-trips per Celery task |
| FR-16 | Performance regressions MUST fail CI when p95 exceeds baseline × threshold | `benchmarks/baselines.json` enforced on nightly |
| FR-17 | Context assembly MUST count tokens before LLM call and truncate deterministically | `context_tokens` ≤ `max_context_tokens` in telemetry |
| FR-18 | LLM calls MUST pass `num_ctx` (Ollama) or respect server `max_model_len` | Default ≥ 16384; never rely on provider default 2048 |
| FR-19 | Token usage MUST be recorded per query (`prompt_tokens`, `completion_tokens`) | Langfuse generation span + telemetry footer |
| FR-20 | Sub-projects MUST communicate only via shared contracts — no direct imports across `query` / `ingest` / `infra` / `inference` / `observability` | Architecture review + package boundary lint |
| FR-21 | `hybrid-rag-ingest` MUST NOT expose MCP tools or HTTP query routes | Ingest admin API only |
| FR-22 | `hybrid-rag-query` MUST NOT enqueue Celery ingest tasks or parse source files | Read-only on index stores + catalog |
| FR-23 | Production MCP MUST validate **`Authorization: Bearer`** — **MCP access token** (`rag_mcp_*`, §7.13) or OIDC JWT when `auth.jwt_bridge=true` | Anonymous `/sse` disabled when `auth.required=true` |
| FR-24 | JWT `sub` MUST map to catalog principal `user:{sub}` for ACL resolution | Contract test with frozen ACL fixture |
| FR-25 | Query pipeline MUST reuse a single pooled client per store (Qdrant, Neo4j, Redis, HTTP inference) | No per-request client construction after warmup |
| FR-26 | Ingest workers MUST batch embed when `len(chunks) > 1` and provider supports batch API | Reduces embed round-trips; enforced in `benchmark_ingest.py` |
| FR-27 | Query MUST enforce per-tenant rate limits on MCP and `/research/stream` | HTTP 429 + `Retry-After`; bypassing BFF still throttled |
| FR-28 | HTTP clients to inference and stores MUST use circuit breakers with configurable thresholds | Open circuit → defined degrade path (§6.3.2), not unbounded retry |
| FR-29 | Ingest MUST auto-pause job enqueue when `celery_queue_depth` exceeds threshold | Protects query TTFT under ingest surge (NFR-18) |
| FR-30 | Per-tenant quotas MUST be enforced at ingest enqueue and query admission | Catalog `tenant_quotas` table; 429/403 on exceed |
| FR-31 | Query MUST support adaptive `search_ef` based on corpus size and latency SLO violation | See [`query/docs/PERFORMANCE.md`](./query/docs/PERFORMANCE.md) §4 |
| FR-32 | Load and soak tests MUST pass release gate thresholds before `rag-v*` tag | §13.1 methodology; 50 concurrent streams minimum soak |
| FR-33 | Kernel, MCP, and HTTP contract changes MUST include **failing or updated tests** in the same change set before merge | Contract tests §19.3; frozen fixtures |
| FR-34 | New pipeline stages and parsers MUST be developed **test-first**: unit test with mocks → implementation → integration test | §19.4; `docs/TESTING.md` |
| FR-35 | Platform MUST maintain audience guides in `docs/` (user, admin, deployment, architect, developer); each sub-project MUST maintain `README.md` + `SPEC.md` | §21.1; [docs/DOCUMENTATION.md](./docs/DOCUMENTATION.md) |
| FR-36 | Architecture and flow diagrams in normative documentation MUST use **Mermaid** (TL-12) | §21.2; PR checklist §21.3 |
| FR-37 | Public application APIs (Python modules, LangGraph nodes, TS exports) MUST include novice-readable docstrings explaining purpose, inputs/outputs, and spec links | §21.4, §23.3; TL-13 |
| FR-38 | Application code in query, ingest, and inference sidecars MUST follow [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) — layout, naming, errors, logging, IF boundaries | §23 |
| FR-39 | New Python modules in application sub-projects MUST pass **Ruff** and **Black** checks before merge when `pyproject.toml` or `make lint` is configured | §23.8; TL-14 |
| FR-40 | When `[signoz].enabled = true`, query and ingest MUST emit `rag_ttft_ms` and `rag_stage_ms` OTLP histograms per §10.5.3 | SigNoz contract tests; E-23 |
| FR-41 | MCP server MUST persist conversation sessions and message history in Postgres when `[sessions].enabled = true` | §7.11; `conversation_sessions` DDL |
| FR-42 | `research_documents` and `POST /research/stream` with `session_id` MUST load prior turns, run RAG, and append user + assistant messages atomically | §6.13.7; contract tests |
| FR-43 | Session read/write MUST enforce `tenant_id` + principal (`user:{sub}`) — cross-user session access returns 404 | §7.11.4; ACL on sessions |
| FR-44 | Every MCP tool and protected HTTP route MUST enforce RBAC when `[rbac].enabled = true` — deny before handler execution | §7.13; `query/app/rbac.py` |
| FR-45 | RBAC permissions MUST come from **MCP token** `permissions[]` when Bearer is `rag_mcp_*`; JWT path MAY use `[rbac.role_templates]` when `jwt_bridge=true` | `mcp_access_tokens` §4.4.3 |
| FR-46 | Data access (ACL) MUST be evaluated **after** RBAC passes | §9.4 |
| FR-47 | MCP token secrets MUST be stored **hashed** (SHA-256); plaintext shown **once** at mint | §7.13.3 |
| FR-48 | Revoked or expired MCP tokens MUST return 401 | `revoked_at`, `expires_at` |

### 2.4 Non-functional requirements

| ID | Category | Target (v1) |
|----|----------|-------------|
| NFR-01 | Availability | `/healthz` 99.9% monthly (single-node prod) |
| NFR-02 | Query latency (GPU) | P95 TTFT < 2s; P95 full answer < 15s |
| NFR-03 | Query latency (CPU dev) | P95 full answer < 45s on `lima_12gb` profile |
| NFR-04 | Ingest throughput | ≥ 50 chunks/s sustained on `gpu_24gb` (embed-bound) |
| NFR-05 | Scale | 10M chunks per tenant; 100 collections per tenant |
| NFR-06 | Security | All external surfaces TLS; secrets never in logs |
| NFR-07 | Observability | 100% of BFF chat messages have trace id in Langfuse or SigNoz |
| NFR-08 | Portability | Laptop dev with Ollama; prod with vLLM or SGLang — same config schema |
| NFR-09 | TTFT (GPU, scoped query) | P50 < 800ms; P95 < 2s (first `token` SSE event) |
| NFR-10 | Retrieval-only latency | P95 < 500ms excl. supervisor + LLM on `gpu_24gb`, collection < 500k chunks |
| NFR-11 | BFF + MCP overhead | P95 < 500ms excl. LLM (auth, SSE connect warm, retrieve, rerank) |
| NFR-12 | Ingest efficiency | Dedup skip rate ≥ 30% on incremental re-ingest of unchanged corpus |
| NFR-13 | Cache effectiveness | Query cache hit rate ≥ 15% on repeated FAQ-style questions (when enabled) |
| NFR-14 | Cold-start | MCP `warmup_clients()` completes in < 30s; first query not > 2× warm query |
| NFR-15 | Context fit | 100% of prod queries assemble prompt within `num_ctx` — zero silent truncation overflows |
| NFR-16 | Prompt token budget | Assembled context ≤ `max_context_tokens`; logged in telemetry as `context_tokens` |
| NFR-17 | Host memory headroom | ≥ 15% free RAM/VRAM under sustained load on target profile |
| NFR-18 | Embed GPU sharing | Ingest MUST NOT reduce query TTFT p95 by > 20% during concurrent peak without throttling | `celery_concurrency` cap or off-peak ingest schedule |
| NFR-19 | Rerank efficiency | With two-stage rerank enabled, full reranker MUST score ≤ `rerank_stage1_top_n` pairs | Default 12 — not full `final_recall_limit` |
| NFR-20 | Resilience | Circuit breaker open on inference MUST resolve within 30s (half-open probe) or route to abstain | No cascading retry storms |
| NFR-21 | Rate fairness | P99 admission latency for rate-limited tenants < 50ms (Redis token bucket) | Excludes LLM time |
| NFR-22 | Degradation | Under load, platform MUST shed optional stages before returning 503 | Degrade ladder §6.3.2 |
| NFR-23 | Soak stability | 2h soak at 50 concurrent scoped queries: error rate < 0.1%, p95 drift < 15% | §13.1 |
| NFR-24 | Error budget | Monthly availability SLO 99.9% with 43m error budget; burn alerts at 2×/6× | §18.14 |
| NFR-25 | Documentation freshness | Behavioral or interface changes MUST update affected audience guides and `SPEC.md` in the **same PR** | §21.3; FR-35 |
| NFR-26 | Code style gates | When `make lint` or CI lint is configured for a sub-project, PRs MUST pass Ruff + Black before merge | §23.8; TL-14 |

---

## 3. Modular architecture

The platform decomposes into **five runtime sub-projects** plus a **shared contract kernel** (`mod-kernel`). Each sub-project has its own config, health surface, CI pipeline, and release cadence. They interact only through well-defined interfaces below.

### 3.1 Module boundary diagram

```mermaid
flowchart TB
    subgraph Clients
        CHAT[mod-chat BFF/UI]
        MCPHOST[MCP Hosts]
    end

    subgraph QUERY_SUB["hybrid-rag-query (sub-project)"]
        MCP[MCP + HTTP Gateway]
        RAG[Query Pipeline]
    end

    subgraph INGEST_SUB["hybrid-rag-ingest (sub-project)"]
        ORCH[Orchestrator]
        CEL[Celery Workers]
    end

    subgraph INFRA_SUB["hybrid-rag-infra (sub-project)"]
        QD[(Qdrant)]
        N4J[(Neo4j)]
        RD[(Redis)]
        MIN[(Object store)]
        PG[(Postgres catalog)]
        KC[Keycloak]
        CAD[Caddy optional]
    end

    subgraph INF_SUB["hybrid-rag-inference (sub-project)"]
        INF[Chat / embed / vision / reranker / smoke LLM]
    end

    subgraph OBS["hybrid-rag-observability (sub-project)"]
        LF[Langfuse]
        SZ[SigNoz / OTLP]
    end

    subgraph KERNEL["mod-kernel — Shared contracts"]
        SCH[Chunk schema]
        EVT[Domain events]
        ACL[Catalog API]
    end

    CHAT -->|HTTP/SSE only| MCP
    MCPHOST --> MCP
    MCP --> RAG
    RAG -->|read| QD
    RAG -->|read| N4J
    RAG -->|read ACL| PG
    RAG --> INF
    Internet -.->|HTTPS /mcp/*| CAD
    CAD --> MCP
    ORCH --> CEL
    CEL -->|write index| QD
    CEL -->|write graph| N4J
    CEL -->|write blobs| MIN
    CEL -->|write catalog| PG
    CEL --> RD
    CEL --> INF

    MCP -.->|OTLP + Langfuse SDK| MOD_OBS
    CEL -.->|OTLP + events| MOD_OBS
    CHAT -.->|OTLP| MOD_OBS

    QUERY_SUB -.-> KERNEL
    INGEST_SUB -.-> KERNEL
```

**Hard boundaries:**

| Rule | Enforcement |
|------|-------------|
| `hybrid-rag-query` never writes Qdrant/Neo4j | Write clients not packaged in query image |
| `hybrid-rag-query` never enqueues Celery ingest tasks | Ingest jobs via `ingest/` admin API only |
| `mod-infra` has no application business logic | IaC + compose/systemd only — **deprecated as deploy unit; use `infra/` sub-project** |
| `hybrid-rag-infra` has no RAG logic | Store provisioning + edge only; separate repo/compose |
| `hybrid-rag-inference` has no RAG logic | Model serving only; separate repo/compose |
| `hybrid-rag-observability` has no RAG logic | Receives telemetry only; separate repo/compose |
| `mod-chat` never connects to Qdrant/Neo4j/Redis | BFF proxies to `hybrid-rag-query` only |

### 3.2 Module responsibilities

| Module | Owns | Does NOT own |
|--------|------|--------------|
| **hybrid-rag-query** | Scope, retrieve, rerank, graph read, answer, MCP tools, SSE, query cache, warmup | Parsing, chunking, index writes |
| **hybrid-rag-ingest** | Connectors, parse/chunk, embed-at-index, dedup, graph write, catalog write, ingest jobs, admin API | User-facing Q&A, MCP research tools |
| **hybrid-rag-infra** | Qdrant, Neo4j, Redis, MinIO, Postgres, Keycloak, Caddy edge, backups, init scripts | RAG pipelines, model weights |
| **hybrid-rag-inference** | vLLM chat/embed/vision, reranker sidecars, smoke LLM, GPU profiles | RAG pipeline logic, index stores |
| **hybrid-rag-observability** | Trace/log/metric ingest, dashboards, alerts | Pipeline logic, index stores |
| **mod-kernel** | Schemas, event types, API contracts | Any runtime service |

### 3.3 Inter-module interfaces

#### IF-1: Index store (Qdrant + Neo4j) — `hybrid-rag-ingest` → `hybrid-rag-query`

| Aspect | Contract |
|--------|----------|
| Writer | `hybrid-rag-ingest` only |
| Reader | `hybrid-rag-query` only |
| Schema | §4.2 chunk payload, §4.3 graph schema |
| Versioning | Immutable `version_id`; query defaults to latest via catalog |
| Compatibility | `index_schema_version` in config; ingest bumps on breaking payload change |

#### IF-2: Catalog API (Postgres) — `hybrid-rag-ingest` writes, `hybrid-rag-query` reads

| Operation | Writer | Reader |
|-----------|--------|--------|
| `documents`, `document_versions`, `ingest_jobs` | ingest | query (read), ingest |
| `acl_grants`, `collections` | ingest + admin | query |
| `tenants` | admin | query, ingest |

`hybrid-rag-query` calls catalog via **read-only DSN** (`CATALOG_DSN_RO`). `hybrid-rag-ingest` uses read-write DSN.

#### IF-3: Domain events (Redis Streams or webhook) — `hybrid-rag-ingest` → `hybrid-rag-query`

Ingest publishes; query subscribes to invalidate caches (optional).

```json
{
  "event": "ingest.completed",
  "tenant_id": "acme-corp",
  "collection_id": "payments-api",
  "version_id": "2026-03-01",
  "chunk_count": 12400,
  "cache_bump": true
}
```

| Event | Publisher | Subscriber action |
|-------|-----------|-------------------|
| `ingest.completed` | hybrid-rag-ingest | hybrid-rag-query: `bump_cache_version()` |
| `ingest.failed` | hybrid-rag-ingest | observability: alert |
| `acl.changed` | admin API | hybrid-rag-query: flush ACL LRU |

#### IF-4: Inference plane — `hybrid-rag-inference` → `hybrid-rag-query` + `hybrid-rag-ingest`

| Caller | Models used | Config URL keys |
|--------|-------------|-----------------|
| hybrid-rag-ingest | embed, vision (VLM) | `vllm_embed_url`, `vllm_vision_url` |
| hybrid-rag-query | embed, LLM, reranker | `vllm_url`, `vllm_embed_url`, `reranker_url`, `reranker_fast_url` |
| CI / contract tests | smoke LLM | `vllm_smoke_url` (optional) |

The **inference sub-project** provisions and scales model servers. Application modules receive **only endpoint URLs** via their own configs — no vLLM Python imports in query/ingest images.

Deploy: [`inference/`](./inference/). Integration: [`inference/docs/INTEGRATION.md`](./inference/docs/INTEGRATION.md).

#### IF-5: Observability — application modules → `hybrid-rag-observability`

| Export | Protocol | Required fields |
|--------|----------|-----------------|
| Traces | OTLP gRPC/HTTP → collector `:4317` → Jaeger UI `:16686` | `module_id`, `trace_id`, `tenant_id` |
| Traces (optional) | Same collector → `otlp/signoz` fan-out → SigNoz backend | Same as traces; see §10.5 |
| Metrics (optional) | OTLP → collector → SigNoz and/or Prometheus `:8889` | Histograms per §10.5.3, §18.5 |
| LLM generations | Langfuse SDK → Langfuse `:3000` | `session_id`, token usage |
| Structured logs | stdout → collector | `module_id`, `request_id` |

Application images contain **SDKs only**. Server stack: [`observability/`](./observability/) (collector, Jaeger, Langfuse; optional SigNoz profile). Docs: [`observability/docs/OTEL.md`](./observability/docs/OTEL.md), [`observability/docs/SIGNOZ.md`](./observability/docs/SIGNOZ.md), [`observability/docs/INTEGRATION.md`](./observability/docs/INTEGRATION.md).

Modules MUST NOT embed Langfuse, Jaeger, or SigNoz server code.

#### IF-6: Identity (OIDC) — `hybrid-rag-infra` (Keycloak) → `mod-chat`, `hybrid-rag-query`

| Aspect | Contract |
|--------|----------|
| Issuer | Keycloak realm `hybrid-rag` — [`infra/docs/KEYCLOAK.md`](./infra/docs/KEYCLOAK.md) |
| Login surface | `mod-chat` BFF + React SPA (authorization code + PKCE) |
| API validation | `hybrid-rag-query` validates JWT on MCP/HTTP when `auth.required=true` |
| JWKS | `{issuer}/protocol/openid-connect/certs` — cached ≤ 1h |
| Principal | JWT `sub` → `user:{sub}`; realm roles → `group:{role}`; RBAC permissions → §7.13 |

**Required JWT claims (access token):**

| Claim | Use |
|-------|-----|
| `sub` | Catalog ACL principal; Langfuse `langfuse_user_id` |
| `iss` | Must match configured `oidc_issuer` |
| `exp` | Reject expired tokens |
| `tenant_id` | Optional custom claim; else resolved from BFF session / MCP arg |

**Pre-configured clients (dev realm import):** `mod-chat` (public), `hybrid-rag-query` (bearer-only).

**Defense in depth:** Caddy `MCP_BEARER_TOKEN` (static) MAY gate `/mcp/sse` at edge; JWT validation + **RBAC** (§7.13) + ACL remain in query for tenant/data binding.

### 3.4 Configuration isolation

Each module loads **its own config file**. No monolithic TOML required at runtime.

| Module | Config env | File |
|--------|------------|------|
| **hybrid-rag-query** | `QUERY_CONFIG` | `query/config/query.toml` |
| **hybrid-rag-ingest** | `INGEST_CONFIG` | `ingest/config/ingest.toml` |
| **hybrid-rag-infra** | `INFRA_CONFIG` | `infra/config/infra.toml` |
| **hybrid-rag-inference** | `INFERENCE_CONFIG` | `inference/config/inference.toml` |
| **hybrid-rag-observability** | `OBS_CONFIG` | `observability/config/observability.toml` |

**Shared values** (must match across modules): `embed_dimension`, `qdrant_collection`, `index_schema_version`, OTLP endpoint, Keycloak `oidc_issuer` (when auth enabled).

### 3.5 Deployment topologies

| Topology | Modules | Use case |
|----------|---------|----------|
| **Laptop dev** | All-in-one compose; processes share localhost | Developer workstation |
| **Split prod** | `query` ×N, `ingest` ×M, managed stores | Enterprise default |
| **Query-only scale** | HPA on `hybrid-rag-query`; ingest batch nightly | Read-heavy |
| **Ingest burst** | Temp ingest workers; query unchanged | Large corpus onboarding |
| **Observability optional** | Langfuse Cloud + collector only | Reduce self-hosted ops |
| **Auth optional (dev)** | Keycloak skipped; MCP auth disabled | Local pipeline testing only |

```mermaid
flowchart TB
    subgraph infra["hybrid-rag-infra"]
        STORES["Qdrant, Neo4j, Redis, MinIO, Postgres, Keycloak"]
        CADDY["Caddy edge (optional)"]
    end

    ING["hybrid-rag-ingest<br/>admin :8020"]
    QRY["hybrid-rag-query<br/>MCP :8010"]
    INFER["hybrid-rag-inference<br/>OpenAI-compatible HTTP"]
    OBS["hybrid-rag-observability"]
    CHAT["mod-chat (optional)"]

    ING -->|read/write| STORES
    QRY -->|read| STORES
    CADDY --> QRY
    MCP_CLIENT["MCP / SSE clients"] --> CADDY
    MCP_CLIENT --> QRY

    ING -->|embed / VLM| INFER
    QRY -->|embed / LLM / rerank| INFER

    QRY --> OBS
    CHAT --> CADDY
```

**Canonical bootstrap:** see §12.5.

### 3.6 Repository layout (recommended)

> **Note:** Shared contracts live under **`modules/`** (`mod-kernel`). Older drafts referenced `kernel/` as a pip package — v0.20 aligns on `modules/SHARED_CONTRACTS.md` + planned `modules/schemas/`.

```text
enterprise-hybrid-rag/
├── modules/                # mod-kernel: SHARED_CONTRACTS.md, schemas/ (planned)
├── docs/                   # audience guides, TESTING, PERFORMANCE, SPEC_ROADMAP
├── packer/                 # root image supply chain (build-all.sh, versions.pkrvars.hcl.example)
├── Makefile                # packer-build-all orchestration
├── query/                  # hybrid-rag-query — MCP, RAG pipeline
│   ├── app/                # rag_graph.py, mcp_server.py, …
│   ├── benchmarks/         # k6, Locust, golden_set.json.example
│   ├── compose/, config/, docs/, packer/
├── ingest/                 # hybrid-rag-ingest
│   ├── app/                # orchestrator.py, tasks.py (stubs)
│   ├── requirements-docling.txt
│   └── compose/, config/, docs/, packer/
├── infra/                  # hybrid-rag-infra — stores + Keycloak + Caddy
│   ├── scripts/            # init-db.sh, init-minio.sh, postgres-init.sh, …
│   ├── keycloak/hybrid-rag-realm.json
│   └── compose/, caddy/, config/, docs/, packer/
├── inference/              # hybrid-rag-inference — vLLM, reranker sidecar
│   ├── reranker/sidecar.py
│   └── compose/, config/, docs/, packer/
├── observability/          # Langfuse, OTel collector, Jaeger
│   ├── dashboards/langfuse-hybrid-rag.json
│   ├── scripts/synthetic_trace.py
│   └── compose/, collector/, docs/, packer/
├── chat-ui/                # mod-chat (optional, planned E-18) — not on disk
└── deploy/helm/            # planned E-19 — not on disk
```

All runtime sub-project config lives **inside** each sub-project directory (`query/config/query.toml`, etc.).

CI: each sub-project has `make health`; root `Makefile` coordinates Packer builds (§12.7).

---

## 3A. Reference architecture (logical view)

> **Module ownership:** §3 above is normative for boundaries. Sections below retain full platform detail; each section header tags the owning module.

### 3A.1 System context

```mermaid
flowchart TB
    subgraph Clients
        CHAT[Enterprise Chat UI]
        MCPHOST[MCP Hosts<br/>Claude Desktop / Cursor / Agents]
        API[Internal APIs / Workflows]
    end

    subgraph Platform["Hybrid RAG Platform"]
        MCP[MCP + HTTP Gateway<br/>research_documents / stream / healthz]
        ING[Ingest Orchestrator<br/>connectors + Celery workers]
        RAG[Query Pipeline<br/>scope → retrieve → rerank → graph → answer]
    end

    subgraph AI["Inference Plane"]
        LLM[Chat LLM]
        EMB[Embedding model]
        VLM[Vision model optional]
        RER[Reranker CrossEncoder]
    end

    subgraph Data["Data Plane"]
        QD[(Qdrant<br/>hybrid vectors)]
        N4J[(Neo4j<br/>structure + refs)]
        RD[(Redis<br/>broker + dedup + cache)]
        MIN[(Object store<br/>images/PDFs)]
        META[(Postgres<br/>catalog + ACL)]
    end

    subgraph Obs["Observability"]
        LF[Langfuse]
        SZ[SigNoz / OTLP]
    end

    CHAT --> MCP
    MCPHOST --> MCP
    API --> MCP
    MCP --> RAG
    ING --> QD
    ING --> N4J
    ING --> MIN
    ING --> RD
    RAG --> QD
    RAG --> N4J
    RAG --> LLM
    RAG --> EMB
    RAG --> RER
    MCP --> LF
    MCP --> SZ
    CHAT --> SZ
```

### 3A.2 Layered responsibilities

| Layer | Responsibility |
|-------|----------------|
| **Connector** | Pull bytes + metadata from source systems (S3, filesystem) |
| **Parse & chunk** | Structure-aware splitting, heading hierarchy |
| **Enrich** | VLM captions, table extraction, link mining |
| **Index** | Embed, upsert Qdrant, MERGE Neo4j, dedup |
| **Catalog** | Document registry, versions, ACL (Postgres) |
| **Scope resolve** | Map query → document set filter |
| **Retrieve** | Hybrid search + optional Neo4j fulltext RRF |
| **Rerank** | Cross-encoder or two-stage fast→full |
| **Graph enrich** | Parent sections, cross-doc refs in LLM context |
| **Generate** | Grounded answer + citations + abstention |
| **Expose** | MCP tools + SSE stream + health |
| **Consume** | BFF multiplexer, threads, OIDC auth |

### 3A.3 Component map

| Component | Responsibility | Stateful? |
|-----------|----------------|-----------|
| MCP + HTTP gateway | Tool dispatch, SSE stream, health | No |
| Ingest orchestrator | Manifest parse, job enqueue, connector poll | Job state in Postgres |
| Celery workers | Parse batches, embed, index, dedup | No |
| Query pipeline | Scope → retrieve → rerank → graph → answer | Optional Redis cache |
| Inference plane | LLM, embed, VLM, reranker (local or HTTP sidecar) | Model weights on GPU host |
| Qdrant | Hybrid vectors + payload indexes | Yes |
| Neo4j | Hierarchy + REFERENCES + optional fulltext | Yes |
| Redis DB 0 | Celery broker | Yes |
| Redis DB 1 | Chunk content-hash dedup | Yes |
| Redis DB 2 | Ingest file registry + optional query cache | Yes |
| Postgres catalog | Tenants, ACL, jobs, chat threads | Yes |
| Object store | PDFs, diagram binaries, presigned URLs | Yes |

---

## 4. Shared contracts (`mod-kernel`)

> **Normative detail:** [`modules/SHARED_CONTRACTS.md`](./modules/SHARED_CONTRACTS.md)  
> **Writers:** `hybrid-rag-ingest`. **Readers:** `hybrid-rag-query`. Neither may extend the schema without a kernel version bump.

### 4.1 Core entities

| Entity | Description | Example |
|--------|-------------|---------|
| **Tenant** | Organizational boundary | `acme-corp` |
| **Collection** | Logical corpus (product line, department, project) | `payments-api`, `hr-policies` |
| **Document** | Stable identity for a source file or page tree | `doc://payments-api/admin-guide` |
| **Version** | Immutable ingest snapshot | `2026-03-01`, `v2.4.0` |
| **Chunk** | Retrieval unit in Qdrant (+ optional Neo4j) | UUID point id |

### 4.2 Chunk payload schema (Qdrant)

All retrieval filters MUST be expressible as Qdrant payload indexes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | string (UUID) | yes | Point id |
| `tenant_id` | string | yes | Tenant isolation |
| `collection_id` | string | yes | Corpus partition |
| `document_id` | string | yes | Stable document key |
| `version_id` | string | yes | Ingest version |
| `title` | string | yes | Document or section title |
| `text` | string | yes | Chunk body |
| `section_id` | string | no | Hierarchical section key |
| `section_title` | string | no | Heading text |
| `parent_section_id` | string | no | Parent in outline |
| `page_number` | int | no | PDF page |
| `chunk_index` | int | no | Ordinal within document |
| `type` | enum | yes | `text` \| `table` \| `code` \| `visual` \| `faq` |
| `language` | string | no | ISO 639-1 |
| `tags` | string[] | no | User or ingest tags |
| `source_uri` | string | no | Original URL/path |
| `source_system` | string | no | `s3`, `filesystem` |
| `acl_principal` | string[] | no | Allowed groups/users |
| `references` | string[] | no | Mined links to other `document_id`s |
| `image_url` | string | no | Object store URL |
| `ingested_at` | datetime | yes | ISO timestamp |
| `content_hash` | string | no | SHA-256 of normalized text |

**Custom metadata:** Namespaced keys `meta.{key}` per collection (max 32 keys; string/number/bool).

### 4.3 Graph schema (Neo4j)

| Node | Key |
|------|-----|
| `Tenant` | `tenant_id` |
| `Collection` | `tenant_id`, `collection_id` |
| `Document` | `document_id` |
| `Version` | `document_id`, `version_id` |
| `Section` | `section_graph_id` |
| `Chunk` | `uuid` (optional fulltext) |

| Relationship | From → To |
|--------------|-----------|
| `OWNS` | Tenant → Collection |
| `CONTAINS` | Collection → Document |
| `HAS_VERSION` | Document → Version |
| `HAS_SECTION` / `HAS_SUBSECTION` | Document/Section → Section |
| `HAS_CHUNK` | Section → Chunk |
| `REFERENCES` | Document/Section → Document |

`section_graph_id` = `{tenant_id}:{collection_id}:{document_id}:{section_id}`.

### 4.4 Catalog tables (Postgres)

| Table | Purpose |
|-------|---------|
| `tenants` | Tenant registry |
| `collections` | Collection metadata + default ACL |
| `documents` | Document registry, latest version pointer |
| `document_versions` | Version history, ingest job id |
| `ingest_jobs` | Status, errors, file counts |
| `acl_grants` | `principal` → collection/document |

Chat product tables: `mcp_servers`, `chat_threads`, `chat_messages` (+ optional `collection_id` pin per thread) — **mod-chat optional**. **MCP-native sessions** use `conversation_sessions` / `conversation_messages` in the catalog (§4.4.2, §7.11) owned by `hybrid-rag-query`.

#### 4.4.1 Normative catalog DDL (v1)

**Migration file:** [`ingest/migrations/001_catalog_v1.sql`](./ingest/migrations/001_catalog_v1.sql)

Apply after `infra/scripts/postgres-init.sh` creates roles (`ingest_rw`, `query_ro`, `query_session_rw`, `query_token_rw`):

```bash
psql "$CATALOG_DSN" -f ingest/migrations/001_catalog_v1.sql
```

| Table | Primary key | Notes |
|-------|-------------|-------|
| `tenants` | `tenant_id` | Tier: `standard` \| `professional` \| `regulated` |
| `tenant_quotas` | `tenant_id` | FK → tenants; §9.3 quota fields |
| `collections` | `(tenant_id, collection_id)` | `default_acl` JSONB |
| `documents` | `(tenant_id, collection_id, document_id)` | `tombstoned` soft-delete |
| `document_versions` | + `version_id` | Immutable version rows; `content_hash` |
| `ingest_jobs` | `job_id` UUID | Status machine FR-10 |
| `acl_grants` | `grant_id` UUID | `principal` → collection/document scope |

**Indexes (normative):** `idx_ingest_jobs_tenant_status`, `idx_acl_grants_lookup`, `idx_documents_tenant_collection` — see migration file. Additional indexes: INF-P2 `postgres-catalog-indexes.sql` (planned).

**Roles:** `ingest_rw` — DDL + DML on catalog. `query_ro` — SELECT on catalog tables. `query_session_rw` — R/W on `conversation_*` only (§4.4.2). `query_token_rw` — R/W on `mcp_access_tokens` (§4.4.3). Table grants applied in `004_grant_query_roles_v1.sql`.

#### 4.4.2 Conversation session DDL (v1)

**Migration file:** [`ingest/migrations/002_conversation_sessions_v1.sql`](./ingest/migrations/002_conversation_sessions_v1.sql)

Apply after `001_catalog_v1.sql`:

```bash
psql "$CATALOG_DSN" -f ingest/migrations/002_conversation_sessions_v1.sql
```

| Table | Primary key | Notes |
|-------|-------------|-------|
| `conversation_sessions` | `session_id` UUID | `tenant_id`, `principal`, title, scope pins, soft-delete |
| `conversation_messages` | `message_id` UUID | FK → session; `role` user \| assistant \| system; `content`; `rag_metadata` JSONB |

**Retention:** `sessions.max_age_days` (default 90) — nightly prune job (E-36). **Quota:** `sessions.max_per_principal` (default 100 active sessions per user).

**DSN:** Query uses `CATALOG_DSN_SESSION` for sessions; `CATALOG_DSN_TOKEN` for `mcp_access_tokens`; `CATALOG_DSN_RO` for catalog reads.

#### 4.4.3 MCP access token DDL (v1)

**Migration:** [`ingest/migrations/003_mcp_access_tokens_v1.sql`](./ingest/migrations/003_mcp_access_tokens_v1.sql)

| Table | PK | Columns |
|-------|-----|---------|
| `mcp_access_tokens` | `token_id` UUID | `tenant_id`, `principal`, `permissions` JSONB, `secret_hash`, `expires_at`, `revoked_at` |

**Grants migration:** [`ingest/migrations/004_grant_query_roles_v1.sql`](./ingest/migrations/004_grant_query_roles_v1.sql) — run after `003_*`.

#### 4.4.4 Migration runner

> **Detail:** [`ingest/docs/MIGRATIONS.md`](./ingest/docs/MIGRATIONS.md)

| Requirement | Normative rule |
|-------------|----------------|
| **Owner** | `hybrid-rag-ingest` — `ingest/app/migrate.py` + `make migrate` |
| **Ordering** | Lexicographic `NNN_*.sql` under `ingest/migrations/` |
| **Tracking** | `schema_migrations(version, applied_at)` table |
| **Lock** | `pg_advisory_lock(742001)` — single migrator |
| **Bootstrap** | Root `make bootstrap` step 3 invokes `cd ingest && make migrate` after infra health |

### 4.5 Qdrant collection schema

**Decision (OD1):** One global collection per deployment with mandatory `tenant_id` payload index — simpler ops; per-tenant collections reserved for regulated isolation tiers.

| Setting | Value | Notes |
|---------|-------|-------|
| Collection name | Configurable; default `enterprise_hybrid_rag` | Single collection per cluster |
| Dense vector | Unnamed default vector; dim = `embed_dimension` | Cosine distance |
| Sparse vector | Named `bm25-text` | Hash-based token indices + TF at ingest; query-time sparse tokens at search |
| `on_disk_payload` | `true` | Required at >1M chunks |
| Quantization | INT8 scalar (optional) | Enable at >5M chunks |
| Payload indexes | `tenant_id`, `collection_id`, `document_id`, `version_id`, `type`, `tags` | All scope filters indexed |
| HNSW `m` | `16` default; `32` at >100k points | Higher = more RAM, better recall |
| HNSW `ef_construct` | `100` default; `256` after full re-ingest | Tune at index time only |
| HNSW `search_ef` | `128` default; `256` for large corpus | Runtime recall vs latency knob |

**Search pattern:** Qdrant prefetch dense + sparse in **one request** → RRF fusion → optional Neo4j fulltext merge (second RRF pass). Use `SearchParams(hnsw_ef=search_ef)` on every query.

**Large corpus checklist (>500k chunks):** `on_disk_payload=true`, INT8 quantization, `search_ef=256`, `hnsw_m=32`, narrow `final_recall_limit`.

### 4.6 Redis partitioning

| DB | Purpose | Key pattern |
|----|---------|-------------|
| 0 | Celery broker + result backend | Celery-managed |
| 1 | Chunk dedup | `dedup:{tenant_id}:{content_hash}` → `uuid` |
| 2 | Ingest file registry | `file:{tenant_id}:{collection_id}:{path}` → `{hash, mtime}` |
| 2 | Query result cache (optional) | `qcache:{sha256(scope+query)}` → serialized `RAGResult` TTL |

### 4.7 JSON schema registry (`modules/schemas/`)

Machine-readable contracts for contract tests, MCP validation, and CI. **Human field lists** remain in §4.2–4.4; schemas are normative for automated validation (E-15).

| Schema file | Validates |
|-------------|-----------|
| [`chunk_payload.v1.json`](./modules/schemas/chunk_payload.v1.json) | Qdrant payload at `index_schema_version=1` |
| [`mcp_research_documents.input.v1.json`](./modules/schemas/mcp_research_documents.input.v1.json) | MCP tool `research_documents` arguments |
| [`mcp_create_conversation_session.input.v1.json`](./modules/schemas/mcp_create_conversation_session.input.v1.json) | MCP tool `create_conversation_session` |
| [`mcp_get_conversation_history.input.v1.json`](./modules/schemas/mcp_get_conversation_history.input.v1.json) | MCP tool `get_conversation_history` |
| [`events.ingest_completed.v1.json`](./modules/schemas/events.ingest_completed.v1.json) | Redis Stream `ingest.completed` event |

**Rule:** Breaking payload changes increment `index_schema_version` and add `chunk_payload.v{N}.json` — do not mutate v1 in place.

**Contract tests MUST:** load schemas from `modules/schemas/` and validate golden fixtures (FR-33, `docs/TESTING.md`).

---

## 5. Ingestion (`hybrid-rag-ingest`)

> **Sub-project:** [`ingest/`](./ingest/) — separate compose, config, CI, release tag (`ingest-v*`).  
> **Normative detail:** [`ingest/SPEC.md`](./ingest/SPEC.md), [`ingest/docs/PIPELINE.md`](./ingest/docs/PIPELINE.md)  
> **Isolated from query:** No MCP server, no `/research/stream`. Publishes `ingest.*` events on completion.

### 5.1 Supported formats (v1)

| Format | Default parser | Strategy |
|--------|----------------|----------|
| PDF | PyMuPDF (`fitz`) | Page + layout blocks; OCR hook for scans |
| PDF (complex) | **Docling** | Tables, multi-column, reading order — `parser_profile = docling` |
| DOCX | python-docx | Heading styles + tables |
| DOCX / PPTX (complex) | **Docling** | Layout-aware export when manifest or profile requests |
| HTML | trafilatura | DOM headings; BeautifulSoup fallback |
| Markdown | markdown-it-py | ATX / setext headings |
| Plain text | stdlib | Paragraph / sliding window |
| RTF, JSON, YAML, XML, CSV | stdlib (+ pandas CSV) | Path / schema / row chunking |
| Images | vision LLM | VLM caption → text chunk; binary in MinIO (`defer_vlm`) |

Detail: [`ingest/docs/PARSERS.md`](./ingest/docs/PARSERS.md), [`ingest/docs/DOCLING.md`](./ingest/docs/DOCLING.md).

### 5.1.1 Parser profiles

| Profile | Libraries | When |
|---------|-----------|------|
| `fast` (default) | PyMuPDF, python-docx, trafilatura, markdown-it-py | Bulk ingest, digital PDFs, NFR-04 throughput |
| `docling` | **Docling** | Scanned tables, slides, multi-column PDFs, complex DOCX/PPTX |
| `auto` | Heuristic router | Digital PDF → fast; low text yield or manifest flag → Docling |

**Rule (TL-10):** Docling runs in the **parser pool** (CPU), not on the embed GPU. Schedule Docling-heavy jobs off-peak when query shares hosts (NFR-18).

Collection manifest override:

```yaml
parser: docling   # per collection in ingest manifest
```

### 5.2 Ingest modes

| Mode | Behavior |
|------|----------|
| **Full** | Re-index collection; new `version_id` |
| **Incremental** | File registry detects new/changed paths by hash |
| **Single document** | API: `POST /admin/ingest/document` |
| **Connector sync** | Scheduled S3 / MinIO |

### 5.3 Pipeline stages

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant P as Parser pool
    participant C as Celery workers
    participant R as Redis dedup
    participant Q as Qdrant
    participant G as Neo4j
    participant S as Object store

    O->>P: Parse file → chunks + metadata
    P->>C: batch_write_task(chunks[])
    C->>R: SHA-256 dedup
    C->>S: Upload visuals
    C->>C: Embed dense + sparse
    C->>Q: Upsert (tenant filter)
    C->>G: MERGE graph
```

### 5.4 Chunking defaults

```toml
[ingest]
max_chunk_tokens = 512
chunk_overlap_tokens = 64
batch_size = 20
parse_workers = 4
embed_parallelism = 4
celery_concurrency = 4
defer_vlm = true
qdrant_upsert_batch = 100      # points per Qdrant upsert call
neo4j_unwind_batch = 50        # nodes per UNWIND transaction
dedup_mget_batch = 100         # Redis MGET keys per round-trip
```

### 5.4.1 Ingest throughput optimizations

| Technique | Config | Impact |
|-----------|--------|--------|
| **Deferred VLM** | `defer_vlm = true` | Parse never blocks on vision model; VLM runs in Celery worker |
| **Parallel parse** | `parse_workers = 2–4` | `ProcessPoolExecutor` across files; CPU-bound |
| **Batch embed** | `embed_parallelism`, batch API | Single `embed(input=[...])` per Celery task |
| **Redis MGET dedup** | `dedup_mget_batch` | Batch hash lookups before embed |
| **Precomputed sparse** | At parse time | Sparse token indices computed once; not re-derived in worker |
| **Bulk Neo4j UNWIND** | `neo4j_unwind_batch` | One transaction per batch vs per-node MERGE |
| **Qdrant batch upsert** | `qdrant_upsert_batch` | Amortize gRPC overhead |
| **Backpressure** | Celery queue depth log | `ingest_backpressure queue_depth=N concurrency=M` — raise concurrency only when queue grows |
| **Off-peak bulk jobs** | Cron / Celery beat | Full reindex off business hours; protects query TTFT (NFR-18) |
| **Embed throttle** | `ingest_max_chunks_per_minute` | Rate-limit during peak query when sharing embed GPU |
| **Async Qdrant upsert** | `wait=false` on bulk | Reduces write latency; query reads eventually consistent within seconds |

**Throughput target:** NFR-04 ≥ 50 chunks/s sustained on `gpu_24gb` when embed-bound.

**Concurrency rule:** `celery_concurrency × embed_parallelism` MUST NOT exceed inference sustained throughput. Start conservative (`2×2`); raise after observing GPU utilization and queue depth.

**Incremental ingest:** File registry (Redis DB 2) skips unchanged files by hash before parse — target NFR-12 dedup skip rate.

### 5.5 Ingest manifest (per collection)

```yaml
tenant_id: acme-corp
collection_id: payments-api
version_id: "2026-03-01"
defaults:
  language: en
  tags: [payments, api]
path_rules:
  - glob: "admin-guide/**"
    document_id_template: "admin-guide"
    title: "Admin Guide"
  - glob: "openapi/*.yaml"
    document_id_template: "openapi-{basename}"
    type: code
acl:
  - principal: "group:payments-team"
    role: read
```

### 5.6 Cross-reference mining

Collections MAY define `reference_patterns` in the manifest — ordered list of regex + target field:

```yaml
reference_patterns:
  - pattern: '\b([A-Z]{2,}-\d{3,})\b'
    target: document_id
  - pattern: 'https://docs\.example\.com/([\w-]+)'
    target: document_id
```

Mined refs populate chunk `references[]` and Neo4j `REFERENCES` edges when the target `document_id` exists in the same collection.

### 5.7 Idempotency and failure handling

| Event | Behavior |
|-------|----------|
| Duplicate chunk hash | Skip Qdrant upsert; reuse existing `uuid` |
| Worker crash mid-batch | Celery retry with exponential backoff (max 3) |
| Parse failure | Log per-file error; job continues; `ingest_jobs.error_count++` |
| Partial collection failure | Job status `completed_with_errors` if `error_count > 0` |
| Full reindex | New `version_id`; prior version points retained until retention policy prunes |

### 5.8 Connector framework (v2 interface)

All connectors implement:

```python
class Connector(Protocol):
    def list_objects(self, since: datetime | None) -> Iterator[SourceObject]: ...
    def fetch_bytes(self, key: str) -> bytes: ...
    def metadata(self, key: str) -> dict[str, str]: ...  # etag, mtime, acl hints
```

| Connector | v1 | Auth | Notes |
|-----------|-----|------|-------|
| Filesystem | yes | OS perms | Dev + air-gapped |
| S3 / MinIO | P2 | IAM keys | Prefix per collection |

Scheduled sync: cron or Celery beat; `connector_sync_interval_minutes` per collection.

---

## 5A. Platform stack integration

Normative detail in dedicated specs — summarized here for the full port picture.

### Inference (`hybrid-rag-inference` → `hybrid-rag-query` + `hybrid-rag-ingest`)

| Port | Service | Spec |
|------|---------|------|
| 8000 | Chat LLM (vLLM) | [`inference/docs/CHAT_LLM.md`](./inference/docs/CHAT_LLM.md) |
| 8001 | Embeddings (vLLM) | shared by query + ingest |
| 8002 | Vision (VLM) | ingest only (`defer_vlm`) |
| 8091 / 8092 | Reranker full / fast | query only |
| 8011 | Smoke / test LLM | CI profile (`PROFILE=dev`) |

Default `inference_provider = "vllm"`. Ollama fallback for laptop dev without the inference stack.

> **Sub-project:** [`inference/`](./inference/) — separate compose, config, CI, release tag (`inf-v*`).

### Langfuse (`hybrid-rag-observability` server; SDK in `hybrid-rag-query`)

| Port | Purpose |
|------|---------|
| 3000 | Langfuse UI + ingest API |
| 4317 | OTLP gRPC (collector ingress) |
| 16686 | Jaeger trace UI |

Env: `LANGFUSE_*`, `OTEL_EXPORTER_OTLP_ENDPOINT`. Stack: [`observability/docs/STACK.md`](./observability/docs/STACK.md).

### Keycloak (`hybrid-rag-infra`)

| Port | Purpose |
|------|---------|
| 8081 (host) | OIDC issuer + admin console |

Realm `hybrid-rag`; clients `mod-chat`, `hybrid-rag-query`. See [`infra/docs/KEYCLOAK.md`](./infra/docs/KEYCLOAK.md).

### Caddy (`hybrid-rag-infra` edge)

| Port | Proxies to |
|------|------------|
| 8080 / 443 | `hybrid-rag-query` MCP at `{mcp_path}/sse` |

Does **not** expose vLLM, Qdrant, or Langfuse publicly by default. See [`infra/docs/CADDY.md`](./infra/docs/CADDY.md).

### Infrastructure sub-project summary (`hybrid-rag-infra`)

> **Sub-project:** [`infra/`](./infra/) — separate compose, config, CI, release tag (`infra-v*`).  
> **Integration:** [`infra/docs/INTEGRATION.md`](./infra/docs/INTEGRATION.md)  
> Application modules use **client libraries + connection URLs** only — no Qdrant/Neo4j server code in RAG images.

| Service | Port | Consumer |
|---------|------|----------|
| Qdrant | 6333 | hybrid-rag-query (R), hybrid-rag-ingest (W) |
| Neo4j | 7687 | hybrid-rag-query (R), hybrid-rag-ingest (W) |
| Redis | 6379 | hybrid-rag-query (cache), hybrid-rag-ingest (broker) |
| MinIO | 9000 | hybrid-rag-ingest (W), hybrid-rag-query (presigned R) |
| Postgres | 5432 | catalog — `query_ro` / `ingest_rw` |
| Keycloak | 8081 | OIDC — `mod-chat`, optional MCP JWT |
| Caddy | 8080 / 443 | public MCP edge (optional `PROFILE=edge`) |

**Bootstrap:** `cd infra && make up && make init-db` (Qdrant + **MinIO buckets/IAM**) · **Health:** `make health` · **Console:** MinIO `:9001`

### Query sub-project summary (`hybrid-rag-query`)

> **Sub-project:** [`query/`](./query/) — separate compose, config, CI, release tag (`query-v*`).  
> **Integration:** [`query/docs/INTEGRATION.md`](./query/docs/INTEGRATION.md)  
> **MCP-first API** — read-only on stores; calls inference via HTTP.

| Surface | Port | Role |
|---------|------|------|
| MCP SSE + HTTP | 8010 | `research_documents`, `/research/stream`, `/healthz` |
| Caddy edge | 8080/443 | Public `/mcp/sse` → query :8010 |

**Bootstrap:** `cd query && make up` (after infra + inference) · **Health:** `make health`

### Ingestion sub-project summary (`hybrid-rag-ingest`)

> **Sub-project:** [`ingest/`](./ingest/) — separate compose, config, CI, release tag (`ingest-v*`).  
> **Integration:** [`ingest/docs/INTEGRATION.md`](./ingest/docs/INTEGRATION.md)  
> **Admin API only** — no MCP, no `/research/stream`.

| Component | Port | Role |
|-----------|------|------|
| Orchestrator | 8020 | `POST /admin/ingest/*`, job enqueue |
| Celery workers | — | parse → embed → Qdrant/Neo4j write |
| Celery beat | — | connector sync (`PROFILE=beat`) |

**Bootstrap:** `cd ingest && make up` (after infra + inference) · **Health:** `make health`

### Inference sub-project summary (`hybrid-rag-inference`)

> **Sub-project:** [`inference/`](./inference/) — separate compose, config, CI, release tag (`inf-v*`).  
> **Integration:** [`inference/docs/INTEGRATION.md`](./inference/docs/INTEGRATION.md)  
> Application modules (`hybrid-rag-query`, `hybrid-rag-ingest`) use **OpenAI-compatible HTTP clients only** — no vLLM imports in application images.

| Service | Port | Consumer |
|---------|------|----------|
| Chat LLM | 8000 | hybrid-rag-query |
| Embeddings | 8001 | hybrid-rag-query, hybrid-rag-ingest |
| Vision | 8002 | hybrid-rag-ingest |
| Reranker / fast | 8091 / 8092 | hybrid-rag-query |
| Smoke LLM | 8011 | CI (`PROFILE=dev`) |

**Profiles:** `dev` (embed + rerankers + smoke LLM, no GPU), `gpu_24gb`, `a100_80gb`.  
**Health:** `cd inference && make health` · **CI smoke:** `make smoke-test`

---

## 6. Query pipeline (`hybrid-rag-query`)

> **Sub-project:** [`query/`](./query/) — separate compose, config, CI, release tag (`query-v*`).  
> **Normative detail:** [`query/docs/PIPELINE.md`](./query/docs/PIPELINE.md)  
> **Read-only stores:** Qdrant scroll/search, Neo4j read sessions, catalog RO DSN. Subscribes to `ingest.completed` for cache invalidation.

### 6.1 Stages (LangGraph)

The query pipeline is a **LangGraph `StateGraph`** (`query/app/rag_graph.py`). Each row is a graph **node**; conditional edges implement skip/abstain logic.

| Node | Stage | Description |
|------|-------|-------------|
| `check_cache` | cache_hit | Optional Redis full-result cache |
| `supervisor` | supervisor | Optional query rewrite (skipped when scope explicit) |
| `embed` | embed | Single dense + sparse vector per request |
| `scope` | scope | Resolve `DocumentScope` |
| `retrieve` | retrieve | Hybrid Qdrant ± Neo4j fulltext RRF |
| `rerank` | rerank | Cross-encoder; optional two-stage |
| `graph_enrich` | graph | Parent sections + cross-refs in context |
| `answer` | answer | Grounded generation + citations |

**Orchestration:** [LangGraph](https://langchain-ai.github.io/langgraph/) · **Run tracing:** [LangSmith](https://docs.smith.langchain.com/) · Detail: [`query/docs/LANGGRAPH.md`](./query/docs/LANGGRAPH.md)

Per-stage `timings_ms` required for observability (SSE telemetry footer + Langfuse attributes).

### 6.1.1 Query latency budget (GPU, scoped, warm)

Target breakdown for P95 on `gpu_24gb` profile, collection < 500k chunks:

| Stage | P95 budget | Skippable when |
|-------|------------|----------------|
| `cache_hit` | < 5ms | — |
| `scope` | < 20ms | Explicit pins in request |
| `supervisor` | < 400ms | `skip_supervisor_when_explicit = true` |
| `embed` | < 80ms | Never (single call) |
| `retrieve` | < 150ms | — |
| `rerank` | < 400ms | Two-stage reduces this |
| `graph` | < 100ms | `graph_enrich_enabled = false` |
| `answer` (TTFT) | < 800ms P50 | Streamed via SSE |
| **Total excl. LLM** | **< 500ms** | Measured as sum of non-answer stages |

BFF + MCP overhead (excl. RAG + LLM): < 50ms auth/DB + < 20ms warm SSE connect = **< 500ms p95** per NFR-11.

### 6.2 Document scope model

```python
@dataclass(frozen=True)
class DocumentScope:
    tenant_id: str
    collection_id: str
    document_ids: tuple[str, ...]      # empty = all in collection
    version_id: str | None             # None = latest
    source: Literal["explicit", "inferred", "broad"]
    inference_score: float | None
    additional_collections: tuple[str, ...]
```

**Scope modes:** `auto` | `require_explicit` | `broad` (admin).

**Explicit pins (MCP / HTTP):**

```json
{
  "tenant_id": "acme-corp",
  "collection_id": "payments-api",
  "document_id": "admin-guide",
  "version_id": "2026-03-01"
}
```

### 6.3 Retrieval parameters

| Parameter | Default |
|-----------|---------|
| `broad_recall_limit` | 50 |
| `final_recall_limit` | 25 |
| `rerank_top_k` | 4 |
| `min_rerank_score` | 0.0 |
| `neo4j_fulltext_enabled` | false |
| `fulltext_top_k` | 15 |
| `skip_supervisor_when_explicit` | true |
| `scope_rerank_mode` | `dense` |
| `scope_rerank_top_n` | 15 |
| `multi_scope_parallelism` | 4 |
| `graph_enrich_enabled` | true |

Qdrant filter always includes `tenant_id`; adds collection/document/version when scoped.

### 6.3.1 Query path optimizations

| Technique | Config | Impact |
|-----------|--------|--------|
| **Skip supervisor** | `skip_supervisor_when_explicit` | Saves 200–800ms when scope pinned via MCP/UI |
| **Dense scope rerank** | `scope_rerank_mode = dense` | Uses Qdrant fusion scores for scope inference; no cross-encoder at scope step |
| **Two-stage rerank** | `reranker_fast` + `rerank_stage1_top_n` | Fast model narrows 25 → 8 before full reranker |
| **Parallel multi-scope** | `multi_scope_parallelism` | Thread pool when `scope_strategy = multi_top_k` |
| **Single embed** | Pipeline invariant | One dense + sparse vector reused for scope + retrieve |
| **HTTP reranker sidecar** | `reranker_url` | Shared GPU process; MCP workers stay lightweight (~1 GB RAM saved each) |
| **Result cache** | `query_cache_enabled` | Full `RAGResult` skip for identical scope+query |
| **SSE streaming** | `/research/stream` | TTFT = first token after retrieve+rerank; user sees progress immediately |
| **Client warmup** | `warmup_clients()` at MCP start | Eliminates cold Qdrant/Neo4j/reranker connection on first query |
| **Inference keep-alive** | `ollama_keep_alive = 30m` | Prevents model unload between requests (Ollama only) |
| **Prefix caching** | vLLM `--enable-prefix-caching` | Speeds repeated system prompts when supported |
| **Parallel retrieve** | `multi_scope_parallelism` | Thread pool for `scope_strategy = multi_top_k` |
| **Qdrant gRPC** | Client config | Prefer gRPC :6334 over REST for lower retrieve latency |
| **Payload filter pushdown** | Always filter `tenant_id` + `collection_id` | Shrinks HNSW search space before RRF |

**Optimization playbook:** [`docs/PERFORMANCE.md`](./docs/PERFORMANCE.md) — profile presets, anti-patterns, benchmark workflow.

**Scope rerank modes:**

- `dense` (default, fast): Qdrant RRF score ranks scope candidates
- `cross_encoder` (accurate, slow): BGE `predict` on `scope_rerank_top_n` candidates — use when scope inference accuracy is critical

**Neo4j fulltext trade-off:** Adds 50–200ms per scoped query; enable only when acronym/section-title recall lift justifies cost (measure via `fulltext_recall_lift` gate).

### 6.3.2 Graceful degradation ladder

Under saturation (GPU queue depth, store latency, or admission control), the query plane MUST shed work in **this order** — never skip ACL or tenant filter:

| Level | Trigger | Action | User-visible |
|-------|---------|--------|--------------|
| L0 | Normal | Full pipeline | Standard answer + sources |
| L1 | `inference_queue_depth` > soft limit OR `retrieve` p95 > budget × 1.5 | Skip `graph_enrich` | Answer without parent-section context |
| L2 | L1 sustained 2 min OR rerank p95 > budget × 2 | Skip full rerank; use dense top-k | Faster answer; lower precision |
| L3 | Embed timeout OR circuit open on embed | Cache-only or abstain if no cache | "Temporarily unable to search" or cached result |
| L4 | Qdrant circuit open | Abstain immediately | `abstained: true`, no LLM call |
| L5 | Admission limit / all circuits open | HTTP 503 `research_ready: false` | Retry after `Retry-After` |

**Config:** `[degradation]` in `query.toml` — enable per level, thresholds, and `degradation_mode` (`auto` \| `disabled`).

**Observability:** Emit `degradation_level` on every query span; alert when L2+ > 5% of traffic for 10 min.

### 6.4 Citations

```json
{
  "document_id": "admin-guide",
  "collection_id": "payments-api",
  "version_id": "2026-03-01",
  "section_id": "3.2.1",
  "section_title": "Authentication",
  "score": 0.87,
  "source_uri": "s3://bucket/admin-guide.pdf",
  "page_number": 42,
  "label": "[payments-api / admin-guide §3.2.1 p.42]"
}
```

### 6.5 Abstention

When `top_rerank_score < min_rerank_score`: abstention message, `abstained: true`, skip LLM generation.

### 6.6 Default answer system prompt

> You are a technical assistant. Answer using ONLY the provided context blocks. Cite sources inline using `[collection / document §section]`. If the context is insufficient, say you cannot confirm from the indexed documents.

Templates stored per `collection_id`: `supervisor`, `answer_system`, `abstention`.

### 6.7 Scope resolution algorithm

```mermaid
flowchart TD
    A[Query + optional pins] --> B{Explicit collection/document/version?}
    B -->|yes| C[source=explicit]
    B -->|no| D{scope_mode}
    D -->|require_explicit| E[ScopeResolutionError]
    D -->|auto| F[Supervisor or catalog inference]
    D -->|broad| G[All collections user can access]
    F --> H{inference_score >= threshold?}
    H -->|yes| I[source=inferred]
    H -->|no| J[Fallback: broad within pinned collection or error]
    C --> K[DocumentScope]
    I --> K
    G --> K
```

**Inference sources (priority order):**

1. MCP/HTTP explicit args (`collection_id`, `document_id`, `version_id`)
2. Collection-specific regex rules in manifest (`scope_patterns`)
3. Supervisor LLM JSON: `{ "collection_id", "document_id", "confidence" }`
4. Catalog keyword match against document titles/tags (cheap fallback)

Default `inference_threshold`: `0.7`. Below threshold → `broad` within tenant or error per `scope_mode`.

**Multi-document scope:** `document_ids` tuple; empty = all documents in collection matching ACL.

### 6.8 Two-stage reranking

When `reranker_fast` is configured:

1. **Stage A:** Fast cross-encoder on full recall pool (`final_recall_limit` → `rerank_fast_top_k`, default 12)
2. **Stage B:** Full cross-encoder on stage-A output (`rerank_top_k`, default 4)

Rerankers MAY be local (`sentence-transformers`) or HTTP sidecars (`reranker_url`, `reranker_fast_url`) for GPU sharing.

### 6.9 Result cache

Optional Redis cache keyed by `sha256(normalized_query + scope_json + config_version)`.

| Setting | Default |
|---------|---------|
| `query_cache_enabled` | `false` |
| `query_cache_ttl_seconds` | 3600 |
| `query_cache_min_rerank_score` | 0.5 |

Cache hits set `from_cache: true` and emit `cache_hit` timing stage. Bypass cache when `request_id` includes `no_cache=1`.

### 6.10 Visual intent

Supervisor or keyword detector flags visual intent when query contains terms like `diagram`, `flowchart`, `screenshot`, `figure`.

When flagged: Qdrant filter adds `type == visual`; graph enrichment includes `image_url` presigned links in context.

### 6.11 Inference plane

| Role | Config key | Providers |
|------|------------|-----------|
| Chat LLM | `models.llm` | Ollama, vLLM, SGLang, OpenAI-compatible |
| Embeddings | `models.embed` | Ollama, vLLM, local HF |
| Vision | `models.vision` | Ollama VLM, vLLM multimodal |
| Reranker | `models.reranker` | Local CrossEncoder, HTTP sidecar |

**Context window:** `models.ollama_num_ctx` or server `--max-model-len` MUST be ≥ 16384 for graph-enriched answers with tables on `gpu_24gb`+. See §6.13 for token budget and profile-specific defaults.

**Memory:** Size inference hosts using §6.14 VRAM/RAM budgets. On ≤16 GB hosts, run **one heavy model at a time** (LLM or VLM or reranker).

**Provider selection:** `models.inference_provider` = `vllm` (default prod) \| `ollama` (dev) \| `sglang` \| `openai`.

> **Inference detail:** vLLM layout, reranker sidecars, profiles, health probes — [`inference/SPEC.md`](./inference/SPEC.md)

| Profile | Typical host | LLM | Embed | `num_ctx` | VRAM |
|---------|--------------|-----|-------|-----------|------|
| `mac_8gb` | 8 GB Mac | `gemma2:9b` | `nomic-embed-text` | 8192 | ~6 GB |
| `lima_12gb` | 12 GB CPU prod | `llama3.2:3b` | `intfloat/e5-base-v2` | 8192 | CPU only |
| `gpu_24gb` | RTX 4090 | `qwen3-coder:32b` | `intfloat/e5-base-v2` | 16384 | ~22 GB |
| `a100_80gb` | A100 80 GB | `Meta-Llama-3.3-70B-Instruct` (SGLang) | `intfloat/e5-base-v2` | 32768 | ~70 GB |

`/healthz` `inference_ok` probes chat + embed endpoints with minimal payloads.

### 6.12 Startup warmup

MCP gateway MUST call `warmup_clients()` before accepting traffic:

| Client | Warmup action |
|--------|---------------|
| Qdrant | `get_collections()` + collection info |
| Neo4j | `verify_connectivity()` |
| Inference | Minimal embed + chat ping |
| Reranker | Load model or probe sidecar `/healthz` |
| Postgres catalog | Connection pool init |

Target: complete within 30s (NFR-14). Log `warmup_ms` per client.

#### 6.12.1 `warmup_clients()` contract

Invoked from FastAPI **lifespan** startup in `mcp_server.py` when `[performance].warmup_on_startup = true` (default).

```mermaid
sequenceDiagram
    participant MCP as mcp_server startup
    participant W as warmup_clients()
    participant Stores as Qdrant Neo4j Redis Catalog
    participant Inf as Inference reranker

    MCP->>W: on application startup
    par parallel probes
        W->>Stores: pool init + health probes
        W->>Inf: minimal embed + chat ping
    end
    W-->>MCP: warmup_ms per client
    MCP-->>MCP: accept traffic /healthz research_ready
```

| Client key | Probe | Failure behavior |
|------------|-------|------------------|
| `qdrant` | `get_collections()` + target collection info | `research_ready=false` (FR-06) |
| `neo4j` | `verify_connectivity()` | degrade L1 (skip graph) if optional; else not ready |
| `redis` | `PING` | cache + rate limit degraded |
| `catalog` | `SELECT 1` on RO pool | `research_ready=false` |
| `inference` | embed 1 token + chat 1 token | `research_ready=false` |
| `reranker` | `GET /healthz` on sidecar | degrade L2 (dense-only rerank) |

**Stub phase:** when `STUB_HEALTH=true`, warmup MAY short-circuit (§1.5). Production **MUST** run full probes.

### 6.13 Context assembly and token budget

The LLM receives a **single system message** containing the grounded context block, plus conversation history (when `session_id` is set — §6.13.7), plus a **user message** with the current query. Without `session_id`, each query is stateless relative to prior turns (v1 default for direct MCP clients).

#### 6.13.7 Conversation history (multi-turn)

When `session_id` is provided on `research_documents` or `/research/stream`, the handler **MUST**:

1. Load the last `max_history_turns` messages from `conversation_messages` (§7.11)
2. Inject trimmed history into the answer LLM call (not into supervisor or embed stages by default)
3. After a successful answer, append `user` + `assistant` rows in one transaction
4. Set `langfuse_session_id = session_id` when Langfuse is enabled

```mermaid
sequenceDiagram
    participant Client as MCP client
    participant MCP as mcp_server
    participant DB as conversation_messages
    participant RAG as run_rag_pipeline

    Client->>MCP: research_documents(session_id, query)
    MCP->>DB: SELECT last N turns
    DB-->>MCP: history[]
    MCP->>RAG: state + history
    RAG-->>MCP: answer + sources
    MCP->>DB: INSERT user + assistant
    MCP-->>Client: markdown response
```

**History token budget** (separate from retrieved-context budget §6.13.1):

| Setting | Default | Purpose |
|---------|---------|---------|
| `max_history_turns` | 10 | Max user+assistant pairs loaded |
| `max_history_tokens` | 2000 | Cap total history text before LLM |
| `history_aware_supervisor` | false | When true, last 2 user turns passed to supervisor for pronoun resolution |
| `persist_assistant_sources` | true | Store `sources` + `timings_ms` in `rag_metadata` JSONB on assistant row |

**LLM message order (with session):**

```
system: {grounded context blocks + cite instructions}
[optional] user/assistant pairs from history (oldest → newest, trimmed)
user: {current query}
```

**Rules:**

- Retrieved chunk text MUST NOT be stored in `conversation_messages` — only user query text and assistant answer prose (citations OK)
- History MUST NOT bypass ACL — session `tenant_id` and scope pins apply to every turn
- Cache key (`qcache:`) MUST include `session_id` when history-aware supervisor is enabled; otherwise session_id excluded from cache key (same query in different sessions may hit cache)
- On `abstained: true`, still persist user message + assistant abstention text

**Stub phase:** When `sessions.enabled = false`, `session_id` is ignored with warning log; no DDL required.

#### 6.13.1 Token budget formula

```
num_ctx (server limit)
├── system_prompt_overhead     ~200–400 tokens (instructions + cite hint)
├── context_blocks             ≤ max_context_tokens (default 12_000)
├── user_query                 ~50–500 tokens
├── generation_reserve         max_answer_tokens (default 2_048)
└── safety_margin              context_safety_margin_tokens (default 512)
```

**Hard rule:** `context_tokens + system_overhead + query_tokens + max_answer_tokens + safety_margin ≤ num_ctx`

If the sum would exceed `num_ctx`, truncate context blocks **before** calling the LLM (never rely on the provider to truncate silently).

#### 6.13.2 Context block structure

Each reranked chunk becomes one block, joined by a separator:

```markdown
##### [payments-api / admin-guide §3.2.1 | Authentication | Score: 0.87]
*Lineage:* `Chapter 3 → 3.2 Authentication`
*Cross-references:* refund-policy, api-keys
🖼️ *Asset:* [https://minio/...](https://minio/...)

Raw Source Block Content:
{chunk text}
```

Blocks are ordered by **descending rerank score**. Graph lineage and cross-refs add ~50–150 tokens per block.

#### 6.13.3 Assembly limits

| Setting | Default | Purpose |
|---------|---------|---------|
| `max_context_tokens` | 12000 | Cap total chunk text + block headers sent to LLM |
| `max_chunks_in_context` | 4 | Matches `rerank_top_k` |
| `max_section_parents` | 2 | Graph enrich ancestry depth per chunk |
| `max_cross_refs_per_block` | 5 | Cap REFERENCE titles listed per block |
| `truncate_table_chunks` | true | Trim wide markdown tables |
| `max_table_rows` | 20 | Rows kept after header when truncating tables |
| `max_code_lines` | 80 | Trim `type=code` chunks beyond N lines |
| `max_answer_tokens` | 2048 | Reserved for completion; passed to inference API |
| `context_safety_margin_tokens` | 512 | Buffer for tokenizer mismatch |
| `token_counter` | `cl100k_base` | Tiktoken encoding for budget accounting |

#### 6.13.4 Truncation policy

When `estimate_tokens(context_blocks) > max_context_tokens`, apply in order:

1. **Drop lowest-scoring chunk** — remove entire block (never partial-drop high-score chunks first)
2. **Truncate tables** — keep header + `max_table_rows` data rows + `[table truncated]` footer
3. **Truncate code** — keep first `max_code_lines` + `[code truncated]` footer
4. **Strip graph lineage** — remove lineage/cross-ref lines; keep raw chunk text
5. **Hard truncate chunk text** — tail-truncate individual blocks proportionally to rerank score

Emit `context_truncated: true` in telemetry when any step fires. Log `context_tokens`, `context_chunks_used`, `context_chunks_dropped`.

#### 6.13.5 Profile-specific context defaults

| Profile | `num_ctx` | `max_context_tokens` | `max_answer_tokens` | Notes |
|---------|-----------|----------------------|---------------------|-------|
| `mac_8gb` | 8192 | 5000 | 1024 | Tight; pin scope; skip supervisor |
| `lima_12gb` | 8192 | 5500 | 1024 | CPU prod; smaller LLM |
| `gpu_24gb` | 16384 | 12000 | 2048 | Default enterprise workstation |
| `a100_80gb` | 32768 | 24000 | 4096 | Large tables + graph lineage fit |

Apply via `[models].profile` or explicit overrides in `[query]`.

#### 6.13.6 Supervisor and embed context isolation

| Stage | Context sent to model | Max tokens |
|-------|----------------------|------------|
| Supervisor | User query only + JSON schema instruction | 1024 |
| Embed | Single query string (optimized) | 512 |
| Reranker | Query + one chunk per `predict` call | 512 per pair |
| Answer LLM | Full assembled system prompt + user query | See budget formula |

Supervisor MUST NOT receive retrieved chunks — prevents context pollution and saves tokens.

### 6.14 Memory model (runtime)

#### 6.14.1 Process memory map

| Process | Typical RSS | Dominant allocation | Tuning |
|---------|-------------|---------------------|--------|
| MCP gateway (×1) | 300–800 MB | Python runtime + HTTP | Sidecar reranker avoids +1 GB per worker |
| Celery worker (×N) | 400–1200 MB each | Parse buffers + embed batch | `celery_concurrency`; don't exceed RAM |
| Reranker sidecar | ~1 GB each | CrossEncoder weights | Shared across MCP + workers |
| vLLM LLM server | 60–90% VRAM | Model weights + KV cache | `--gpu-memory-utilization 0.90` |
| vLLM embed server | 2–4 GB VRAM | Embedding model | Dedicated port; don't colocate with 70B |
| Qdrant | 4–32+ GB RAM | Vectors + HNSW + payload | `on_disk_payload`, INT8 quant |
| Neo4j | 2–8 GB heap + pagecache | Graph nodes | JVM sizing §12.2 |
| Redis | 256 MB–2 GB | Dedup keys + cache | `maxmemory` + `allkeys-lru` for cache DB |

#### 6.14.2 GPU VRAM budget per profile

| Profile | Total VRAM | LLM | Embed | Vision | Reranker | Headroom |
|---------|------------|-----|-------|--------|----------|----------|
| `mac_8gb` | 8 GB | 5–6 GB (9B Q4) | CPU/Ollama shared | defer VLM | CPU MiniLM | < 1 GB — **one model at a time** |
| `gpu_24gb` | 24 GB | 16 GB (32B Q4) | 2 GB (dedicated port) | 4 GB (ingest only) | 1 GB sidecar | ~1 GB |
| `a100_80gb` | 80 GB | 70 GB (70B FP8) | 4 GB | 4 GB | 2 GB dual sidecar | ~0 GB — monitor KV growth |

**Rule (≤16 GB hosts):** Never run LLM + VLM + full reranker concurrently. Use `defer_vlm=true` and reranker sidecar. Set `ollama_keep_alive` only for the active model on memory-constrained hosts.

#### 6.14.3 System RAM budget (single-node prod)

| Component | `lima_12gb` (12 GB VM) | `gpu_24gb` (32 GB host) |
|-----------|------------------------|-------------------------|
| OS + Caddy + BFF | 1.5 GB | 2 GB |
| Qdrant | 2 GB | 8 GB |
| Neo4j | 2.5 GB | 6 GB |
| Redis + Postgres | 0.5 GB | 1 GB |
| MCP + Celery (×2) | 1.5 GB | 3 GB |
| Inference (CPU/GPU) | 4 GB | 16 GB host RAM + 24 GB VRAM |
| **Headroom target** | **≥ 1.5 GB** | **≥ 4 GB** |

#### 6.14.4 KV cache and concurrent queries

LLM VRAM grows with concurrent sequences: `KV_cache ≈ 2 × num_layers × hidden × num_ctx × batch × dtype`.

| Setting | Recommendation |
|---------|----------------|
| vLLM `--max-num-seqs` | 8–16 on 24 GB; 32+ on A100 |
| Ollama `num_ctx` | Lower to 8192 on 8 GB when TTFT degrades |
| BFF concurrent streams | Default 2 per user; aligns with KV budget |
| Ingest during peak query | Throttle `celery_concurrency` — embed competes for GPU |

Log `kv_cache_usage_percent` from vLLM metrics when available; alert > 85%.

#### 6.14.5 Ollama memory semantics

| Setting | Effect |
|---------|--------|
| `keep_alive = 30m` | Model stays loaded; VRAM/RAM occupied until timeout |
| `keep_alive = 0` | Unload after request; next query pays cold-start |
| `keep_alive = -1` | Never unload; use only on dedicated inference hosts |

On `mac_8gb`: use `keep_alive = 5m` for chat model only; unload embed between ingest batches if memory pressure detected.

### 6.15 Context and memory observability

**Per-query telemetry (required):**

| Field | Example | Purpose |
|-------|---------|---------|
| `context_tokens` | 8420 | Tokens in assembled context |
| `context_chunks_used` | 4 | Blocks included |
| `context_chunks_dropped` | 0 | Blocks removed by truncation |
| `context_truncated` | false | Any truncation policy fired |
| `prompt_tokens` | 9100 | From inference API |
| `completion_tokens` | 340 | From inference API |
| `num_ctx` | 16384 | Server limit in effect |

**Memory metrics (SigNoz/node exporter):**

| Metric | Alert |
|--------|-------|
| `process_resident_memory_bytes{job="mcp"}` | > 2 GB |
| `container_memory_usage_bytes{container="qdrant"}` | > 85% of limit |
| `nvidia_gpu_memory_used_bytes` | > 90% for 5 min |
| `neo4j_heap_used_percent` | > 80% |

---

## 7. MCP & HTTP gateway (`hybrid-rag-query`)

> **Sub-project:** [`query/`](./query/)  
> **Normative detail:** [`query/docs/MCP.md`](./query/docs/MCP.md), [`query/docs/HTTP.md`](./query/docs/HTTP.md), [`query/docs/STREAMING.md`](./query/docs/STREAMING.md)  
> **Deploy artifact:** `hybrid-rag-query` container / `hybrid-rag-mcp.service`

### 7.1 Principles

1. MCP tools for discrete operations; HTTP for streaming, probes, and **session management**
2. Transports: `stdio` + `sse`
3. **Stateless handlers** — no in-memory session state; conversation history in Postgres when `[sessions].enabled` (§7.11)
4. Tenant from JWT or explicit `tenant_id`

#### 7.1.1 Transport matrix

| Transport | Host | Use case | Auth |
|-----------|------|----------|------|
| **SSE** | `/sse` via Caddy or `:8010` | Cursor, Claude Desktop, mod-chat multiplexer | `rag_mcp_*` Bearer (§7.13) or OIDC JWT when `jwt_bridge=true` |
| **stdio** | MCP host subprocess | Local IDE integration | Env `MCP_ACCESS_TOKEN` (`rag_mcp_*`) or `TENANT_ID` + dev bypass when `auth.required=false` |
| **HTTP** | `/research/stream`, `/healthz`, `/sessions*`, `/admin/mcp/tokens` | BFF streaming, probes, admin | `rag_mcp_*` or JWT per §7.10 |

**Normative:** All three transports invoke the same `run_rag_pipeline()` backend — no divergent business logic per transport.

### 7.2 Server identity

```
name: enterprise-hybrid-rag
version: 1.0.0
description: Hybrid RAG over ingested enterprise documents
```

### 7.3 Required tools

#### `research_documents`

| Argument | Required | Description |
|----------|----------|-------------|
| `query` | yes | User question |
| `tenant_id` | yes* | *From auth if omitted |
| `collection_id` | no | Pin corpus |
| `document_id` | no | Pin document |
| `version_id` | no | Pin version |
| `tags` | no | Tag filter |
| `request_id` | no | Correlation |
| `session_id` | no | Conversation session UUID — load history + persist turn (§7.11) |
| `create_session_if_missing` | no | Create session when `session_id` omitted (default false) |
| `langfuse_session_id` | no | Session grouping; SHOULD equal `session_id` |
| `langfuse_user_id` | no | User id |
| `langfuse_trace_id` | no | 32-hex trace id |

**Returns:** Markdown: answer + **Sources** + telemetry footer.

#### `list_indexed_documents`

Markdown table: document_id, title, latest version, chunk count, ingested_at.

#### `visualize_document_graph`

Mermaid flowchart; args: tenant, collection, document, optional section, max_nodes.

#### `get_document_metadata`

JSON: title, tags, source_uri, acl, chunk stats.

#### 7.3.1 MCP tool JSON schemas

Input schemas **MUST** validate against files in [`modules/schemas/`](./modules/schemas/) before handler execution.

| Tool | Input schema | Output contract |
|------|--------------|-----------------|
| `research_documents` | `mcp_research_documents.input.v1.json` | Markdown §7.8 (not JSON Schema — fixture tests) |
| `create_conversation_session` | `mcp_create_conversation_session.input.v1.json` | JSON `{ session_id, created_at }` |
| `get_conversation_history` | `mcp_get_conversation_history.input.v1.json` | JSON message array |
| `list_indexed_documents` | TBD `mcp_list_indexed_documents.input.v1.json` | Markdown table |
| `get_document_metadata` | TBD | JSON object |
| `visualize_document_graph` | TBD | Mermaid string |

**`research_documents` validation errors:**

| Condition | HTTP / MCP error | `error.kind` |
|-----------|------------------|--------------|
| Missing `query` | 400 | `validation` |
| Empty `query` | 400 | `validation` |
| `query` > 8000 chars | 400 | `validation` |
| Missing `tenant_id` when auth disabled | 400 | `validation` |
| Invalid JWT | 401 | `auth` |
| JWT missing `tenant_id` claim | 403 | `auth` |
| Collection not in catalog | 404 | `not_found` |

### 7.4 Optional admin tools

`list_collections`, `search_snippets`, `explain_scope` — require **`mcp.admin.*`** permissions (§7.13). `trigger_reindex` is **not** implemented in query — use ingest admin API (ingest role `ingest_rw`).

### 7.5 HTTP routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/healthz` | GET | Store + inference readiness |
| `/research/stream` | POST | SSE token stream |
| `/sessions` | POST, GET | Create / list conversation sessions (§7.11) |
| `/sessions/{session_id}` | GET, PATCH, DELETE | Session metadata |
| `/sessions/{session_id}/messages` | GET | Paginated history |

**SSE events:** `token`, `sources`, `telemetry`, `done`, `error`.

### 7.6 Health schema

```json
{
  "status": "ok",
  "research_ready": true,
  "stores_ready": true,
  "checks": {
    "qdrant_ok": true,
    "neo4j_ok": true,
    "redis_ok": true,
    "inference_ok": true,
    "catalog_ok": true
  }
}
```

### 7.7 Error kinds

| Kind | HTTP | User-facing message pattern |
|------|------|----------------------------|
| `scope_resolution` | 422 | Cannot determine which documents to search |
| `validation` | 400 | Missing or invalid argument |
| `auth` | 401 | Missing or invalid JWT / bearer |
| `forbidden` | 403 | Valid identity but insufficient RBAC permission (§7.13) |
| `not_found` | 404 | Collection or document not indexed |
| `inference` | 503 | AI backend unavailable |
| `internal` | 500 | Unexpected error (no stack trace to client) |

### 7.8 MCP markdown response contract

`research_documents` returns markdown in this **stable order** (BFF parsers depend on it):

```markdown
{answer prose with inline citations}

**Sources:**
1. [payments-api / admin-guide §3.2.1 p.42] — Authentication (score 0.87)
2. ...

---
*🔍 **MCP Search Telemetry:** Resolved scope: payments-api / admin-guide (explicit) | Expanded Query: `API key rotation` | Recall candidates: 25 | Reranked: 4 | Context: 8420 tokens (4 chunks, truncated=false) | Tokens: prompt=9100 completion=340 | Timings: embed=45ms, retrieve=120ms, rerank=380ms, graph=90ms, llm=2100ms*
```

Frozen fixtures MUST be checked in CI; breaking changes require coordinated BFF parser updates.

### 7.9 SSE stream contract

Each event is one SSE line: `data: {json}\n\n`

| `type` | Payload fields | When |
|--------|----------------|------|
| `token` | `text: string` | Each LLM token |
| `sources` | `markdown: string` | After retrieval; before answer completes |
| `telemetry` | `markdown: string` | After answer; includes scope + timings |
| `done` | _(none)_ | Stream complete |
| `error` | `message: string` | Fatal; stream ends |

Request body mirrors MCP args plus `request_id`, `langfuse_*` fields. W3C `traceparent` header propagated to downstream spans.

### 7.10 Auth on MCP SSE

**Layered model (production multi-tenant):**

| Layer | Mechanism | Config |
|-------|-----------|--------|
| Edge (optional) | Static bearer on `/mcp/sse` | `caddy.mcp_bearer_token` |
| Application | OIDC JWT validation | `auth.required`, `auth.oidc_issuer`, `auth.jwks_uri` |
| Tenant binding | JWT claim or MCP arg | `tenant_id` required on all research calls |

**Decision (OD5):** Static bearer is **config-driven** — useful for dev and service-to-service; **not sufficient alone** for user-level ACL (OD9).

**OIDC flow (mod-chat → query):**

```mermaid
sequenceDiagram
    participant Browser
    participant KC as Keycloak
    participant BFF as mod-chat BFF
    participant Query as hybrid-rag-query

    Browser->>KC: OIDC PKCE login
    KC-->>Browser: JWT
    Browser->>BFF: Session + JWT
    BFF->>Query: Bearer JWT + traceparent + tenant_id + langfuse_session_id
    Query->>Query: Validate JWT + ACL + rate limits
```

**Dev mode:** `auth.required=false` — no JWT; `tenant_id` from MCP args only (never in production MT).

**Prod mode:** Valid `rag_mcp_*` Bearer required (or JWT when `jwt_bridge=true`); `tenant_id` and `principal` from token row.

#### 7.10.1 Auth layering decision tree

```mermaid
flowchart TD
    REQ[Incoming MCP or /research/stream request]
    REQ --> APP[hybrid-rag-query]
    APP --> AUTH{auth.required?}
    AUTH -->|false dev| TENANT[tenant_id from args]
    AUTH -->|true prod| HDR{Bearer prefix?}
    HDR -->|rag_mcp_*| TOK[Validate token row + permissions]
    HDR -->|JWT + jwt_bridge| JWT[JWKS + role templates]
    HDR -->|other| REJECT1[401]
    TOK --> RBAC{Tool permission?}
    JWT --> RBAC
    RBAC -->|no| REJECT2[403]
    RBAC -->|yes| ACL[ACL + rate limits]
    TENANT --> ACL
    ACL --> RAG[run_rag_pipeline]
```

| Credential | Use |
|------------|-----|
| **`rag_mcp_*`** | **Primary** — auth + RBAC on token row (§7.13) |
| OIDC JWT | Optional mod-chat bridge |
| Caddy static bearer | Optional edge only (OD5) |

**Decision (OQ5):** Token + optional JWT validation **inline** in query — no auth sidecar.

### 7.11 Conversation sessions (persistence & management)

> **Detail:** [`query/docs/SESSIONS.md`](./query/docs/SESSIONS.md) · **DDL:** §4.4.2 · **Pipeline:** §6.13.7

The MCP server **MUST** offer first-class **conversation session** APIs so MCP hosts (Cursor, Claude Desktop, custom agents) and mod-chat can maintain multi-turn history without a separate BFF database. Handlers remain **horizontally scalable** — session state lives in Postgres, not process memory (FR-41).

#### 7.11.1 Design principles

| # | Principle |
|---|-----------|
| 1 | **MCP-first** — session CRUD as MCP tools; HTTP routes mirror for BFF |
| 2 | **Opt-in** — `[sessions].enabled` in `query.toml`; when false, `session_id` ignored |
| 3 | **Principal-scoped** — every session row binds `tenant_id` + `principal` (`user:{sub}` from JWT) |
| 4 | **Scope inheritance** — session-level `collection_id` / `document_id` / `version_id` pins apply to all turns unless overridden per message |
| 5 | **Observability link** — `langfuse_session_id` SHOULD equal `session_id` for cost-per-thread drill-down |
| 6 | **No chunk leakage** — `conversation_messages` stores query/answer text only; retrieved chunks stay ephemeral |

```mermaid
flowchart TB
    subgraph Clients["MCP hosts + mod-chat"]
        IDE[Cursor / Claude Desktop]
        BFF[mod-chat BFF]
    end

    subgraph Query["hybrid-rag-query"]
        MCP[MCP tools + HTTP]
        SESS[session_store.py]
        RAG[run_rag_pipeline]
    end

    PG[(conversation_sessions\nconversation_messages)]

    IDE --> MCP
    BFF --> MCP
    MCP --> SESS
    SESS --> PG
    MCP --> RAG
    RAG --> SESS
```

#### 7.11.2 Session MCP tools

| Tool | Purpose | Auth |
|------|---------|------|
| `create_conversation_session` | New session; optional title + scope pins | JWT required (prod) |
| `list_conversation_sessions` | Paginated list for current principal | JWT |
| `get_conversation_history` | Messages for one `session_id` | JWT + owner check |
| `update_conversation_session` | Title, scope pins, metadata | JWT + owner |
| `delete_conversation_session` | Soft-delete (`deleted_at`) | JWT + owner |
| `research_documents` | RAG + auto-append when `session_id` set | JWT + session owner |

**`create_conversation_session` arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `title` | no | Display label; default first-query truncation |
| `collection_id` | no | Default scope pin for session |
| `document_id` | no | Default document pin |
| `version_id` | no | Default version pin |
| `metadata` | no | JSON object (max 4 KB) — client tags, MCP host id |

**Returns:** `{ "session_id": "<uuid>", "created_at": "<iso>" }`

**`list_conversation_sessions` arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `limit` | no | Default 20; max 100 |
| `cursor` | no | Opaque pagination cursor |
| `include_deleted` | no | Default false |

**Returns:** Markdown table: `session_id`, `title`, `updated_at`, `message_count`, scope pins.

**`get_conversation_history` arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `session_id` | yes | UUID |
| `limit` | no | Default 50 messages; max 200 |
| `before_message_id` | no | Cursor for older messages |

**Returns:** JSON array of `{ message_id, role, content, created_at, rag_metadata? }`.

**`research_documents` — session fields (additions):**

| Argument | Required | Description |
|----------|----------|-------------|
| `session_id` | no | Load history + persist turn; creates implicit session when `create_session_if_missing=true` |
| `create_session_if_missing` | no | Default false; when true with new UUID omitted, server creates session |

Input schema: [`mcp_research_documents.input.v1.json`](./modules/schemas/mcp_research_documents.input.v1.json).

#### 7.11.3 HTTP session routes

Mirror MCP tools for mod-chat and integration tests:

| Route | Method | Purpose |
|-------|--------|---------|
| `/sessions` | POST | Create session (body = create tool args) |
| `/sessions` | GET | List sessions (`?limit=&cursor=`) |
| `/sessions/{session_id}` | GET | Session metadata + optional `?include_messages=true` |
| `/sessions/{session_id}` | PATCH | Update title / scope pins |
| `/sessions/{session_id}` | DELETE | Soft-delete |
| `/sessions/{session_id}/messages` | GET | Paginated history |
| `/research/stream` | POST | Existing; accepts `session_id` — persists on `done` |

All routes require same auth as MCP (§7.10). Response shapes match MCP tool JSON returns.

#### 7.11.4 Security and ACL

| Rule | Behavior |
|------|----------|
| **Ownership** | `principal` on session MUST match JWT `sub` → `user:{sub}` (FR-43) |
| **Cross-tenant** | `tenant_id` on session MUST match JWT `tenant_id` or MCP arg |
| **Not found** | Wrong owner or deleted session → **404** (not 403 — avoid session enumeration) |
| **Service accounts** | Machine principals `service:{client_id}` MAY own sessions when JWT carries `client_credentials` grant — catalog allowlist (future E-37) |
| **Audit** | Emit `session.created`, `session.deleted`, `session.message.appended` audit events |

**Dev mode (`auth.required=false`):** `principal` defaults to `user:dev` or explicit `principal` MCP arg (dev only).

#### 7.11.5 `rag_metadata` on assistant messages

JSONB stored on assistant rows for UI replay without re-parsing markdown:

```json
{
  "sources": [{ "document_id": "...", "section_id": "...", "score": 0.87 }],
  "timings_ms": { "embed": 45, "retrieve": 120, "rerank": 380, "answer": 2100 },
  "abstained": false,
  "from_cache": false,
  "scope": { "collection_id": "payments-api", "document_id": "admin-guide" },
  "context_tokens": 8420,
  "request_id": "..."
}
```

#### 7.11.6 Configuration (`query.toml`)

```toml
[sessions]
enabled = true
max_history_turns = 10
max_history_tokens = 2000
history_aware_supervisor = false
persist_assistant_sources = true
max_per_principal = 100
max_age_days = 90
create_session_if_missing_default = false
```

**DSN:** `CATALOG_DSN_SESSION` — Postgres role `query_session_rw` (INSERT/UPDATE/DELETE on `conversation_*` only).

#### 7.11.7 mod-chat integration

When `[sessions].enabled = true` on query, mod-chat **SHOULD**:

1. Call `create_conversation_session` or `POST /sessions` on thread create
2. Pass `session_id` on every `POST /research/stream` / MCP `research_documents`
3. Use `get_conversation_history` for thread reload — **not** a separate `chat_messages` table (optional local cache OK)

Legacy `chat_threads` / `chat_messages` in mod-chat remain optional for UI-only metadata; **MCP session store is source of truth** when enabled.

### 7.12 Rate limiting and admission control (platform)

Rate limits apply at **hybrid-rag-query** — not only mod-chat BFF (FR-27). Direct MCP and `/research/stream` clients MUST be throttled.

| Limit | Key | Default (standard tier) | Response |
|-------|-----|-------------------------|----------|
| Queries per tenant per minute | `tenant_id` | 120 | HTTP 429 |
| Queries per user per minute | `tenant_id` + `sub` | 30 | HTTP 429 |
| Concurrent streams per user | `sub` | 3 | HTTP 429 |
| Concurrent streams per tenant | `tenant_id` | 50 | HTTP 429 |
| Embed tokens per tenant per day | `tenant_id` | 10M | HTTP 403 quota |

**Implementation:** Redis token bucket (`rlimit:` namespace per SHARED_CONTRACTS §6). Check **before** LangGraph entry — cheap admission.

**Headers:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After` on 429.

**Enterprise tiers:** Override defaults via catalog `tenant_quotas` (§9.3) — `regulated` tier may have lower QPS but dedicated inference pool.

### 7.13 Role-Based Access Control — token-based (MCP)

> **Detail:** [`query/docs/RBAC.md`](./query/docs/RBAC.md) · **DDL:** §4.4.3 · **ACL:** §9.4

**MCP query uses token-based RBAC:** callers present `Authorization: Bearer rag_mcp_{token_id}.{secret}`. The token record carries **`tenant_id`**, **`principal`**, and **`permissions[]`** — RBAC is enforced from the token, not from live Keycloak lookups per request.

OIDC JWT remains an **optional bridge** for mod-chat when `auth.jwt_bridge=true` (§7.13.6).

#### 7.13.1 Why tokens for MCP

| Approach | MCP hosts (Cursor, Claude Desktop) | mod-chat BFF |
|----------|-----------------------------------|--------------|
| OIDC PKCE per request | Poor fit | Natural for login |
| **`rag_mcp_*` access token** | **Primary** | Mint per user; forward Bearer |
| Caddy static bearer | Edge gate only | Dev/S2S |

#### 7.13.2 Auth + RBAC flow

```mermaid
flowchart TD
    REQ[MCP / HTTP request]
    REQ --> HDR{Authorization Bearer?}
    HDR -->|no| E401[401 auth]
    HDR -->|rag_mcp_*| TOK[Lookup mcp_access_tokens]
    TOK -->|invalid/expired/revoked| E401
    TOK -->|ok| CTX[AuthContext from token row]
    HDR -->|JWT + jwt_bridge| JWT[Validate JWKS → map roles]
    JWT --> CTX
    CTX --> RBAC{permission for tool?}
    RBAC -->|no| E403[403 forbidden]
    RBAC -->|yes| RL[Rate limit → handler → ACL]
```

#### 7.13.3 MCP access token format

```text
rag_mcp_{token_id}.{secret}
```

| Part | Notes |
|------|-------|
| `token_id` | UUID — DB PK; safe in logs |
| `secret` | Random — SHA-256 hashed at rest; **never logged** |

```http
Authorization: Bearer rag_mcp_550e8400-e29b-41d4-a716-446655440000.x7K9mN2pQ8vR4sT1wY6zA3bC5dE0fG
```

Validation: lookup row → constant-time hash compare → build `AuthContext` from **`permissions` on the row**.

#### 7.13.4 Permission strings

| Permission | Tools / routes |
|------------|----------------|
| `mcp.research` | `research_documents`, `/research/stream` |
| `mcp.catalog.read` | `list_indexed_documents`, `get_document_metadata` |
| `mcp.graph.read` | `visualize_document_graph` |
| `mcp.session.read` / `.write` | Session tools, `/sessions*` |
| `mcp.admin.collections` | `list_collections` |
| `mcp.admin.diagnostics` | `search_snippets`, `explain_scope` |
| `mcp.admin.tokens` | Mint / revoke / list tokens |

Wildcards: `mcp.admin`, `mcp.session`, `mcp.*`.

#### 7.13.5 Role templates (mint-time only)

Templates expand to `permissions[]` **when the token is created** — frozen until revoked.

| Template | Permissions |
|----------|-------------|
| `viewer` | catalog.read, graph.read, session.read |
| `user` | viewer + research + session |
| `collection-admin` | user + `mcp.admin` |
| `admin` | `mcp.*` |

**Mint** (`POST /admin/mcp/tokens`, requires `mcp.admin.tokens`) — full OpenAPI: [`query/docs/TOKEN_ADMIN.md`](./query/docs/TOKEN_ADMIN.md):

```json
{
  "tenant_id": "acme-corp",
  "principal": "user:alice",
  "label": "Alice Cursor",
  "role_template": "user",
  "expires_in_days": 90
}
```

Response includes `access_token` **once**. Bootstrap: `python -m app.cli mint-mcp-token --template admin`.

#### 7.13.6 OIDC JWT bridge (optional)

When `auth.jwt_bridge=true`, Keycloak JWTs are accepted; `realm_access.roles` → permissions via `[rbac.role_templates]` at **request time** (unlike frozen token permissions).

#### 7.13.7 Tool permission map

| Tool / route | Permission |
|--------------|------------|
| `research_documents`, `/research/stream` | `mcp.research` |
| Catalog tools | `mcp.catalog.read` |
| `visualize_document_graph` | `mcp.graph.read` |
| Session tools | `mcp.session.read` / `.write` |
| Admin tools | `mcp.admin.*` |
| Token admin | `mcp.admin.tokens` |
| `GET /healthz` | none |

#### 7.13.8 Implementation

| Module | Role |
|--------|------|
| `token_store.py` | Mint, validate, revoke |
| `auth.py` | Parse Bearer; token or JWT |
| `rbac.py` | `require_permission(ctx, perm)` |

```toml
[auth]
required = true
jwt_bridge = true
mcp_token_prefix = "rag_mcp_"

[rbac]
enabled = true

[rbac.role_templates]
user = ["mcp.catalog.read", "mcp.graph.read", "mcp.session", "mcp.research"]
admin = ["mcp.*"]
```

#### 7.13.9 Errors

| Condition | Code |
|-----------|------|
| Missing/invalid/revoked token | 401 `auth` |
| Valid token, missing permission | 403 `forbidden` |

OTel: `mcp.authz.check` with `authz.method=mcp_token|jwt`, `authz.token_id`.

#### 7.13.10 Token admin HTTP API

> **Normative OpenAPI:** [`query/docs/TOKEN_ADMIN.md`](./query/docs/TOKEN_ADMIN.md) · **Schemas:** `mcp_access_token_mint.*.v1.json`

| Route | Permission | Purpose |
|-------|------------|---------|
| `POST /admin/mcp/tokens` | `mcp.admin.tokens` | Mint token; return `access_token` once |
| `GET /admin/mcp/tokens` | `mcp.admin.tokens` | List tokens (no secrets) |
| `POST /admin/mcp/tokens/{token_id}/revoke` | `mcp.admin.tokens` | Revoke token |

---

## 8. Chat UI and BFF (`mod-chat`, optional client)

> **Not a core platform module.** Consumes `hybrid-rag-query` exclusively. Replaceable with any MCP host or direct API client.

### 8.1 Stack

- React SPA (SSE, scope bar, document catalog, MCP admin)
- Express BFF (OIDC via **infra Keycloak**, MCP multiplexer, Langfuse traces)
- Postgres (threads, messages, MCP registry)

### 8.2 UI components

| Component | Role |
|-----------|------|
| `ScopeBar` | collection + document + version pins |
| `DocumentCatalogPanel` | Indexed documents via BFF |
| `AdvancedChatViewport` | SSE chat + citations + telemetry |
| `McpAdminPanel` | MCP server CRUD |

### 8.3 BFF flow

`POST /api/threads/:id/messages` → Langfuse `bff.chat.message` → `POST /research/stream` with **`session_id`** (MCP session UUID — §7.11) → optional local UI cache of `rag_metadata`.

When query `[sessions].enabled = true`, BFF **SHOULD** map `thread_id` ↔ `session_id` 1:1 and use MCP session APIs as source of truth.

### 8.4 BFF endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/collections` | Tenant collections |
| `GET /api/collections/:id/documents` | Catalog |
| `POST /api/threads` | Create thread → `create_conversation_session` on query |
| `GET /api/threads/:id/messages` | Load history → `get_conversation_history` |
| `POST /api/threads/:id/messages` | + `session_id`, `collection_id`, `document_id`, `version_id` |

### 8.5 MCP multiplexer

- Pooled SSE clients per server id (~10 min idle)
- `/healthz` probe every 120s
- W3C traceparent + Langfuse id forwarding

### 8.6 Error UX (chat)

| Condition | UI state | User message |
|-----------|----------|--------------|
| MCP unreachable | Connection error | Research service is unavailable. Try again later. |
| `inference_ok: false` | Degraded | AI backend is starting or offline. |
| Empty index | Empty corpus | No documents indexed for this collection yet. |
| `abstained: true` | Insufficient evidence | I could not find enough relevant content to answer confidently. |
| `scope_resolution` | Scope error | Please select a collection or document. |

### 8.7 Rate limits (BFF)

| Limit | Default |
|-------|---------|
| Messages per user per minute | 20 |
| Concurrent streams per user | 2 |
| Response on exceed | HTTP 429 + `Retry-After` |

---

## 9. Security (cross-cutting, per-module enforcement)

| Module | Surface | Mechanism |
|--------|---------|-----------|
| hybrid-rag-query | MCP, `/research/stream` | JWT + **RBAC** (§7.13) + ACL; OIDC JWKS (prod); optional Caddy bearer |
| hybrid-rag-ingest | `/admin/ingest/*` | Service account; no public internet |
| hybrid-rag-infra | TLS, network, identity | Caddy edge, Keycloak realm, internal store network |
| observability sub-project | Dashboards | SSO; no PII in traces |
| mod-chat | BFF | Keycloak OIDC; mints/forwards `rag_mcp_*` to query |

ACL enforcement at **query** (read) and **ingest** (write `acl_principal` on chunks): see §9.4. **RBAC** gates tool access at MCP boundary (§7.13).

### 9.4 Authorization model (RBAC + ACL)

> **RBAC detail:** §7.13 · **ACL DDL:** §4.4 · **Principals:** [SHARED_CONTRACTS.md](./modules/SHARED_CONTRACTS.md) §8

#### 9.4.1 Principal resolution

From **MCP access token** (primary):

```text
tenant_id  ← token row
principal  ← token row (e.g. user:alice)
permissions ← token row (RBAC)
principals_for_acl = { principal } ∪ { group:* from ACL grants matching user }
```

From **JWT bridge** (optional):

```text
principals = { user:{sub} }
           ∪ { group:{role} for role in realm_access.roles }
           ∪ { group:{group} for group in groups claim }
permissions ← map roles via [rbac.role_templates] at request time
```

#### 9.4.2 ACL evaluation (data plane)

After RBAC permits `mcp.research`:

1. Resolve explicit `collection_id` / `document_id` from MCP args or session pins
2. Load `acl_grants` for all principals × tenant
3. If collection has `default_acl` or document-level grants → build allow-list of `(collection_id, document_id?)`
4. Qdrant filter: `tenant_id` AND (`acl_principal` SHOULD match any principal OR chunk has no ACL field)
5. Catalog list tools (`list_indexed_documents`) apply same filter before scroll

**Deny-by-default:** Secured collection with no matching grant → **empty catalog / zero retrieval** — not 403 (prevents title leakage, FR-03).

#### 9.4.3 Combined decision matrix

| RBAC | ACL | User experience |
|------|-----|-----------------|
| deny | — | 403 `forbidden` — cannot invoke tool |
| allow | deny (no grants) | 200 with empty results / "no documents" |
| allow | allow | Normal RAG response |

#### 9.4.4 Admin ACL management

| Action | Who | Surface |
|--------|-----|---------|
| Grant `group:team` read on collection | `collection-admin` or `admin` | Ingest admin API `POST /admin/acl/grants` (E-16) |
| Revoke grant | `admin` | `DELETE /admin/acl/grants/{id}` |
| View effective ACL | `mcp.admin.collections` | `list_collections` includes grant summary |

ACL changes emit `acl.changed` → query flushes in-process LRU (§18 cache).

#### 9.4.5 Testing requirements

| Test | Validates |
|------|-----------|
| `test_rbac_research_denied_for_viewer.py` | `viewer` cannot call `research_documents` |
| `test_rbac_admin_tools_require_admin.py` | `user` denied `list_collections` |
| `test_acl_empty_results_not_403.py` | No grant → empty retrieve, not forbidden |
| `test_principal_group_acl.py` | `group:payments-team` grant allows retrieval |

**ACL enforcement flow (retrieve path):**

1. Resolve JWT `sub` + group claims → principal set (`user:{sub}`, `group:{name}`)
2. Postgres `acl_grants` → allowed `(collection_id, document_id)` tuples
3. Build Qdrant `should` filter on `acl_principal` OR match if chunk has no ACL (inherits collection default)
4. Deny-by-default when collection has ACL and principal not in grant list

**Audit events:** `query.executed`, `ingest.completed`, `acl.changed`, `mcp.tool.called`, `session.created`, `session.deleted`, `session.message.appended`, `connector.sync`, `version.pruned`.

**PII hook (optional):** `ingest.pii_redaction_hook` — pluggable function before embed; default passthrough.

### 9.1 Data lifecycle

| Policy | Default (OD2) | Behavior |
|--------|---------------|----------|
| Version retention | Keep last 3 versions per document | Nightly job deletes older Qdrant points + Neo4j version nodes |
| Document tombstone | Soft-delete in catalog | Points removed on next full reindex or explicit purge API |
| Tenant offboarding | Admin API | Purge all tenant points, graph nodes, object store prefix |
| Backup | Daily Qdrant snapshot + Neo4j dump + Postgres WAL | RPO 24h; RTO 4h (single-node target) |

### 9.2 OIDC and JWT contract (IF-6)

**Realm:** `infra/keycloak/hybrid-rag-realm.json` (dev) — production imports equivalent claim mappers.

#### Claim map (normative)

| Claim | Type | Required (prod) | Used for |
|-------|------|-----------------|----------|
| `sub` | string | yes | ACL principal `user:{sub}` |
| `tenant_id` | string | yes* | Qdrant filter, catalog scope |
| `iss` | string | yes | Issuer validation |
| `aud` | string | yes | Client audience |
| `exp` / `iat` | number | yes | Token lifetime |
| `realm_access.roles` | string[] | no | **RBAC** permission resolution (§7.13.3) |
| `groups` | string[] | no | Optional; map to `group:{name}` principals for ACL |
| `email` | string | no | Audit logs only — never in chunk payloads |
| `preferred_username` | string | no | Audit / Langfuse user id |

\*When `auth.required=true`, `tenant_id` **MUST** come from JWT unless service account uses scoped client credentials with embedded claim. BFF **MUST NOT** override JWT `tenant_id` with a different query param (tenant injection prevention).

#### Validation errors (normative)

| Error code | HTTP | When |
|------------|------|------|
| `invalid_token` | 401 | Malformed JWT, bad signature, expired |
| `invalid_issuer` | 401 | `iss` ≠ configured `oidc_issuer` |
| `invalid_audience` | 401 | `aud` not in allowed clients |
| `missing_tenant_claim` | 403 | No `tenant_id` in token or args |
| `tenant_mismatch` | 403 | Arg `tenant_id` ≠ JWT claim |
| `forbidden` | 403 | Missing RBAC permission for tool/route |

**Implementation:** `query/app/auth.py` (planned) — JWKS cache TTL 300s; refresh on `kid` miss.

**Token propagation:** BFF sends `Authorization: Bearer <access_token>` to `POST /research/stream` and MCP tools. W3C `traceparent` + `langfuse_*` headers preserved.

**Keycloak deployment:** self-hosted in `infra/compose` (default) or external IdP (OQ4) with same claim contract.

**Session vs stateless:** BFF MAY use server-side OIDC session after login; query validates JWT per request. **Conversation history** persists in Postgres via MCP session APIs (§7.11) when enabled — not in query process memory.

**Decision (OQ5):** Inline JWKS in query process — not a separate auth sidecar (§7.10.1).

### 9.3 Per-tenant quotas and isolation tiers

| Quota | Catalog field | Enforced at | Default (standard) |
|-------|---------------|-------------|-------------------|
| Max chunks | `max_chunks` | ingest pre-upsert | 10M |
| Max collections | `max_collections` | ingest enqueue | 100 |
| Query QPS | `query_qps` | query admission | 2/s (120/min) |
| Concurrent streams | `max_concurrent_streams` | query SSE | 50 |
| Storage bytes | `max_storage_bytes` | MinIO pre-PUT | 500 GB |
| Embed tokens / day | `max_embed_tokens_day` | ingest + query embed | 10M |

**Tiers:**

| Tier | Isolation | Performance profile |
|------|-----------|---------------------|
| `standard` | Shared Qdrant collection + `tenant_id` filter | Default quotas; shared inference |
| `professional` | Higher quotas; priority ingest queue | Dedicated Celery queue name |
| `regulated` | Per-tenant Qdrant collection (optional); dedicated embed GPU | Stricter audit; lower shared contention |

Schema: `modules/SHARED_CONTRACTS.md` §12. Admin API: `PUT /admin/tenants/{id}/quotas`.

**Fairness (NFR-18):** When ingest approaches `max_embed_tokens_day`, throttle workers before query TTFT degrades > 20%.

---

## 10. Observability (`hybrid-rag-observability`)

> **Sub-project:** [`observability/`](./observability/) — separate compose, config, CI, and release tag (`obs-v*`).  
> **Integration:** [`observability/docs/INTEGRATION.md`](./observability/docs/INTEGRATION.md)  
> **OTel:** [`observability/docs/OTEL.md`](./observability/docs/OTEL.md) — collector, Jaeger, SDK contract  
> **SigNoz:** [`observability/docs/SIGNOZ.md`](./observability/docs/SIGNOZ.md) — optional APM profile §10.5  
> Application modules (`hybrid-rag-query`, `hybrid-rag-ingest`, `mod-chat`) ship **SDKs/exporters only** — no Langfuse, Jaeger, or SigNoz server code in application images.

| Signal | Langfuse | Jaeger (OTel) | SigNoz (optional) |
|--------|----------|---------------|-------------------|
| LLM + token usage | yes | — | partial |
| RAG stage latency | child spans | spans | attributes |
| MCP/BFF HTTP | trace names | spans | spans |
| Session drill-down | sessionId | trace correlation | trace correlation |

**Trace names:** `bff.chat.message`, `mcp.research_stream`, `rag_pipeline`, `store/qdrant/retrieve`, `store/neo4j/graph`, `store/redis/cache_lookup`.

**SLOs (recommended):** 99.9% healthz; P95 TTFT < 2s GPU; P95 full answer < 15s.

**Structured log (query path):**

```
rag_stage_ms supervisor=120 embed=45 scope=8 retrieve=95 rerank=380 graph=90 answer=2100 from_cache=false abstained=false request_id=abc query='How do I...'
```

**Dashboards:** Jaeger service/operation search; SigNoz (optional): TTFT p95, MCP error rate, citation count per query, cache hit rate, ingest chunks/min, Celery queue depth.

**Langfuse sessions:** Group by `langfuse_session_id` (chat thread) for cost-per-conversation drill-down.

### 10.4 OTel span catalog (LangGraph alignment)

Normative mapping for E-06 — implement in `app/telemetry.py` and LangSmith `langsmith_config.py`.

| OTel span name | LangGraph node / route | Parent span | Key attributes |
|----------------|------------------------|-------------|----------------|
| `mcp.sse.connect` | `/sse` handshake | — | `mcp.transport=sse` |
| `mcp.research_documents` | MCP tool handler | — | `tenant_id`, `tool`, `session_id?` |
| `mcp.authz.check` | RBAC pre-hook | MCP/HTTP span | `authz.permission`, `authz.allowed` |
| `session.load_history` | Before RAG when `session_id` set | MCP/HTTP span | `session_id`, `turn_count` |
| `session.append_turn` | After successful answer | `rag_pipeline` | `session_id`, `message_count` |
| `http.research_stream` | `POST /research/stream` | — | `tenant_id`, `request_id` |
| `rag_pipeline` | `run_rag_pipeline` root | HTTP/MCP span | `collection_id`, `document_id` |
| `rag.node.check_cache` | `node_check_cache` | `rag_pipeline` | `from_cache` |
| `rag.node.supervisor` | `node_supervisor` | `rag_pipeline` | `scope_source` |
| `rag.node.embed` | `node_embed` | `rag_pipeline` | `embed_ms` |
| `rag.node.scope` | `node_scope` | `rag_pipeline` | `scope_source` |
| `rag.node.retrieve` | `node_retrieve` | `rag_pipeline` | `chunk_count` |
| `rag.node.rerank` | `node_rerank` | `rag_pipeline` | `abstained` |
| `rag.node.graph` | `node_graph_enrich` | `rag_pipeline` | `graph_ms` |
| `rag.node.answer` | `node_answer` | `rag_pipeline` | `stub`, `context_tokens` |
| `store.qdrant.retrieve` | Qdrant client | `rag.node.retrieve` | `search_ef`, `tenant_id` |
| `store.neo4j.read` | Neo4j client | `rag.node.graph` | `hop_depth` |
| `inference.embed` | httpx embed call | `rag.node.embed` | `model` |
| `inference.chat` | httpx chat stream | `rag.node.answer` | `model`, `ttft_ms` |

**Langfuse mapping:** `rag_pipeline` → trace; each `rag.node.*` → span; token usage on `inference.chat` generation.

**Ingest (OTLP only):** `ingest.job.batch_write`, `ingest.parser.parse_file` — optional LangSmith on Celery (LG-5).

### 10.5 SigNoz (optional APM profile)

> **Sub-project detail:** [`observability/docs/SIGNOZ.md`](./observability/docs/SIGNOZ.md) · **Collector overlay:** [`observability/collector/otel-collector-config.signoz.yaml`](./observability/collector/otel-collector-config.signoz.yaml)

**SigNoz** is an **optional** observability backend for **HTTP/APM traces**, **histogram metrics**, and **SLO alerting** when Jaeger UI and Prometheus alone are insufficient. It **complements** Langfuse (LLM cost, generations, sessions) — it does **not** replace Langfuse for token accounting.

#### 10.5.1 When to enable

| Scenario | Default (Jaeger + Langfuse) | Enable SigNoz (`PROFILE=signoz`) |
|----------|----------------------------|----------------------------------|
| Local dev / stub phase | sufficient | optional |
| GPU enterprise single-node | Jaeger for trace debug | **recommended** — TTFT p95, MCP error rate, ingest throughput dashboards |
| Production SLO alerting | Langfuse + logs | **recommended** — `QueryP95High`, export failure alerts (§10.5.6) |
| Regulated / air-gapped | self-hosted Jaeger | self-hosted SigNoz stack or collector → internal SigNoz endpoint |
| Langfuse Cloud only | OTLP → Jaeger | SigNoz SaaS via collector `otlp/signoz` exporter |

**Rule (TL-05, IF-5):** Applications **MUST** export to the **single primary OTel collector** (`OTEL_EXPORTER_OTLP_ENDPOINT`). SigNoz is a **downstream fan-out** from the collector — never a second SDK endpoint in app images.

#### 10.5.2 Architecture and routing

```mermaid
flowchart LR
    subgraph Apps["Application modules SDK only"]
        Q[hybrid-rag-query]
        I[hybrid-rag-ingest]
        C[mod-chat BFF]
    end

    subgraph OBS["hybrid-rag-observability"]
        COL[OTel Collector :4317]
        JG[Jaeger :16686]
        LF[Langfuse :3000]
        SZC[signoz-otel-collector optional]
        SZUI[SigNoz UI :8080 optional]
    end

    Q -->|Langfuse SDK| LF
    C -->|Langfuse SDK| LF
    Q -->|OTLP| COL
    C -->|OTLP| COL
    I -->|OTLP| COL
    COL -->|traces default| JG
    COL -. PROFILE=signoz .-> SZC
    SZC --> SZUI
    COL -->|metrics| PROM[Prometheus :8889 optional]
```

| Deployment mode | Compose / config | Trace backends |
|-----------------|------------------|----------------|
| **Default** | `make up` (no profile) | Collector → Jaeger only |
| **SigNoz sidecar** | `make up PROFILE=signoz` | Collector → Jaeger **and** `otlp/signoz` → `signoz-otel-collector` |
| **Managed SigNoz** | `SIGNOZ_OTLP_ENDPOINT` env on collector | Collector → Jaeger + SaaS OTLP endpoint |
| **Metrics profile** | `PROFILE=metrics` | Prometheus scrapes collector `:8889` (orthogonal to SigNoz) |

Mount collector config for SigNoz fan-out:

```bash
# observability/.env
COLLECTOR_CONFIG=collector/otel-collector-config.signoz.yaml
SIGNOZ_OTLP_ENDPOINT=signoz-otel-collector:4317
```

Bootstrap:

```bash
cd observability && make up PROFILE=signoz
# or from root:
make observability-up OBS_PROFILE=signoz
```

#### 10.5.3 Normative metrics (OTLP histograms)

When SigNoz profile is enabled in an environment, application and collector pipelines **SHOULD** emit these instruments (names stable for dashboards E-23):

| Metric | Type | Labels | Source | Alert (§10.5.6) |
|--------|------|--------|--------|-----------------|
| `rag_ttft_ms` | Histogram | `module_id`, `tenant_id` (optional) | query inference stream | p95 > 2000 ms |
| `rag_stage_ms` | Histogram | `stage`, `module_id` | query pipeline stages | p95 > budget × 1.5 |
| `mcp_request_duration_ms` | Histogram | `tool`, `status` | MCP handler | error rate > 1% |
| `query_cache_hit_total` / `query_cache_miss_total` | Counter | `module_id` | cache node | hit rate informational |
| `ingest_chunks_per_second` | Gauge | `collection_id` (no per-tenant in v1) | ingest worker | < 50% baseline 10 min |
| `celery_queue_depth` | Gauge | `queue` | ingest broker | > 500 for 5 min |
| `qdrant_search_latency_ms` | Histogram | `operation` | Qdrant client | p95 > 200 ms |
| `otel_export_errors_total` | Counter | `exporter` | collector self-telemetry | > 1% export failure |

**Cardinality rule:** No per-`document_id` or per-`chunk_id` labels (OBS-P2, §18.5). `tenant_id` on metrics is optional and SHOULD be sampled or aggregated in high-QPS prod.

**FR-40:** When `observability.toml` `[signoz].enabled = true`, query and ingest **MUST** emit `rag_ttft_ms` and `rag_stage_ms` (or equivalent span-derived metrics) via OTLP; missing instruments fail observability contract tests.

#### 10.5.4 Ports and services

| Service | Port | Profile | Notes |
|---------|------|---------|-------|
| SigNoz UI | **8080** | `signoz` or full SigNoz stack | Dev compose may use collector sidecar only — UI when full stack deployed |
| `signoz-otel-collector` | 4317 (internal) | `signoz` | Receives fan-out from primary collector |
| Primary OTLP ingress | 4317 / 4318 | always | Apps target **primary** collector only |
| Jaeger UI | 16686 | always | Remains default trace UI in dev |

> **Note:** Full self-hosted SigNoz (ClickHouse + query service) is **out of compose scope** for v1 dev scaffold; production MAY deploy [SigNoz Helm](https://github.com/SigNoz/charts) and point `SIGNOZ_OTLP_ENDPOINT` at that ingress.

#### 10.5.5 Dashboards as code (E-23)

Normative dashboard files under `observability/dashboards/`:

| File | Panels | Audience |
|------|--------|----------|
| `signoz-query-latency.json` | TTFT p50/p95, `rag_stage_ms` by stage, MCP duration, cache hit rate | SRE / platform |
| `signoz-ingest-throughput.json` | chunks/s, Celery queue depth, parse errors, embed latency | ingest ops |
| `langfuse-hybrid-rag.json` | LLM cost, token usage (existing) | product / cost |

Import via SigNoz UI **or** API when E-23 automation lands. Dashboard JSON **MUST** use metric names from §10.5.3.

#### 10.5.6 Alerts

Rules live in [`observability/alerts/signoz-rules.yaml`](./observability/alerts/signoz-rules.yaml) (export to SigNoz alertmanager or UI):

| Alert | Condition | Severity |
|-------|-----------|----------|
| `QueryP95High` | `rag_ttft_ms` p95 > 2s for 5m | warning |
| `TraceExportFailure` | `otel_export_errors_total` rate > 1% for 5m | critical |
| `IngestStalled` | `celery_queue_depth` > 500 for 5m | warning |
| `McpErrorRateHigh` | MCP 5xx rate > 1% for 5m | warning |

Retention: `[retention].signoz_days` in `observability.toml` (default 30 dev, 90 prod).

#### 10.5.7 Health and bootstrap integration

| Plane | Command | Pass criteria (SigNoz enabled) |
|-------|---------|--------------------------------|
| observability | `cd observability && make up PROFILE=signoz && make health` | Collector `:13133`, Jaeger `:16686`, Langfuse `:3000`; SigNoz UI `:8080` when full stack present |
| synthetic trace | `make synthetic-trace` | Span visible in **Jaeger**; when SigNoz configured, same `trace_id` searchable in SigNoz |

See §12.5 bootstrap step 5 — observability plane; optional `PROFILE=signoz` for GPU enterprise profile (§12 Production).

---

## 11. Configuration (per-module)

Env vars are **per-module** (see §3.4). Legacy monolith: set `HYBRID_RAG_CONFIG` only for all-in-one dev.

| Module | Config file | Key sections |
|--------|-------------|--------------|
| **query** | `query/config/query.toml` | `[models]`, `[query]`, `[services]`, Langfuse SDK env |
| **ingest** | `ingest/config/ingest.toml` | `[ingest]`, `[connectors]`, OTLP env |
| **infra** | `infra/config/infra.toml` | `[qdrant]`, `[neo4j]`, `[keycloak]`, `[caddy]` — **not in RAG app repos** |
| **inference** | `inference/config/inference.toml` | Models, ports, GPU profiles |
| **observability** | `observability/config/observability.toml` | Langfuse, collector, Jaeger, optional SigNoz |

**Cross-module invariants** (must match):

| Key | Modules | Value |
|-----|---------|-------|
| `embed_dimension` | ingest, query, infra | e.g. `768` |
| `qdrant_collection` | ingest, query, infra | e.g. `enterprise_hybrid_rag` |
| `index_schema_version` | ingest, query | e.g. `1` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | all | collector URL |

**Hardware profiles:** `mac_8gb`, `lima_12gb`, `gpu_24gb`, `a100_80gb`.

**Performance TOML example:**

```toml
[qdrant]
hnsw_m = 16
hnsw_ef_construct = 100
search_ef = 128
enable_payload_indexes = true

[services]
ollama_keep_alive = "30m"   # Ollama only; vLLM uses server-side scheduling

[query]
skip_supervisor_when_explicit = true
scope_rerank_mode = "dense"
multi_scope_parallelism = 4
rerank_stage1_top_n = 12
query_cache_enabled = false
graph_enrich_enabled = true
max_context_tokens = 12000
max_answer_tokens = 2048
context_safety_margin_tokens = 512
token_counter = "cl100k_base"
num_ctx = 16384                    # mirrors [models].ollama_num_ctx

[models]
ollama_num_ctx = 16384

[ingest]
batch_size = 32
parse_workers = 2
embed_parallelism = 2
celery_concurrency = 2
defer_vlm = true
qdrant_upsert_batch = 100
neo4j_unwind_batch = 50

[performance]
warmup_on_startup = true
warmup_clients = ["qdrant", "neo4j", "inference", "reranker", "catalog"]
ingest_backpressure_warn_depth = 100
reranker_sidecar_url = ""   # http://127.0.0.1:8091 when set
# Tuning playbooks: docs/PERFORMANCE.md
```

**Minimal `[models]` example:**

```toml
[models]
llm = "meta-llama/Llama-3.2-3B-Instruct"
embed = "intfloat/e5-base-v2"
vision = "Qwen/Qwen2-VL-7B-Instruct"
reranker = "BAAI/bge-reranker-large"
reranker_fast = "cross-encoder/ms-marco-MiniLM-L-6-v2"
embed_dimension = 768
ollama_num_ctx = 16384
inference_provider = "vllm"
profile = "gpu_24gb"

[query]
scope_mode = "auto"
inference_threshold = 0.7
query_cache_enabled = false
neo4j_fulltext_enabled = false
```

---

## 12. Deployment (sub-projects)

> **Stores + edge:** [`infra/`](./infra/) · **Inference:** [`inference/`](./inference/) · **Observability:** [`observability/`](./observability/)  
> **Application modules:** `hybrid-rag-query` and sub-projects connect via URLs in their own configs — no embedded store, ingest, or model server processes in the query image.

### Local dev ports (suggested)

| Service | Port |
|---------|------|
| MCP SSE (direct) | 8010 |
| **Caddy** (public MCP) | 8080 / 443 |
| **vLLM LLM** | 8000 |
| **vLLM embed** | 8001 |
| **vLLM vision** | 8002 |
| **Reranker / fast** | 8091 / 8092 |
| **Smoke LLM** | 8011 |
| Qdrant | 6333 |
| Neo4j | 7687 |
| Redis | 6379 |
| MinIO | 9000 |
| **Keycloak** | 8081 |
| **Jaeger** | 16686 |
| **OTLP** | 4317 / 4318 |
| Chat BFF | 4000 |
| Chat UI | 5173 |
| **Langfuse** | 3000 |
| **SigNoz UI** (optional) | 8080 |

### 12.5 Canonical bootstrap runbook

**Order matters** — later steps depend on URLs and schemas from earlier stacks.

**Root Makefile (preferred):**

```bash
make env
make bootstrap INFERENCE_PROFILE=gpu_24gb
make health
make synthetic-trace    # optional step 8
```

#### 12.5.1 Unified health matrix

| Plane | Command | Pass criteria |
|-------|---------|---------------|
| **Root** | `make health` | All rows below succeed |
| infra | `cd infra && make health` | Qdrant, Neo4j, Redis, MinIO, Postgres, Keycloak reachable |
| inference | `cd inference && make health` | Chat `:8000` + embed `:8001` OpenAI `/models` or health script |
| observability | `cd observability && make health` | Langfuse `:3000`, collector `:4317`, Jaeger `:16686`; SigNoz `:8080` when `PROFILE=signoz` + full stack |
| ingest | `cd ingest && make health` | Orchestrator `/admin/healthz` 200 |
| query | `cd query && make health` | `/healthz` → `research_ready: true` (or stub per §1.5) |

**Manual steps (equivalent to `make bootstrap`):**

| Step | Command | Health gate |
|------|---------|-------------|
| 1. Network | `cd infra && make network` | `docker network inspect hybrid-rag-net` |
| 2. Stores + identity | `make up && make init-db` | `make health` |
| 3. Catalog DDL | `cd ingest && make migrate` (or psql `001`–`004`) | tables + grants exist |
| 3b. Session DDL | included in `002_*` when `[sessions].enabled` | `conversation_*` |
| 3c. Token DDL + grants | included in `003_*`, `004_*` when `[rbac].enabled` | `mcp_access_tokens` + role grants |
| 4. Inference | `cd ../inference && make up PROFILE=gpu_24gb` | `make health` |
| 5. Observability | `cd ../observability && make up` | `make health`; Langfuse API keys |
| 6. Ingest | `cd ../ingest && make up` | orchestrator health |
| 7. Query | `cd ../query && make up` | `/healthz` `research_ready` |
| 8. Edge (optional) | `make bootstrap INFRA_EDGE=true` | Caddy `/mcp/sse` |
| 9. Smoke | `make synthetic-trace` | Jaeger span visible |

Copy Langfuse keys from step 5 into `query/.env`. Configure Keycloak users before mod-chat.

### 12.6 Sub-project release tags and compatibility

Each sub-project tags independently. Application releases MUST declare compatible infra/inference/obs versions.

| Sub-project | Tag pattern | Example |
|-------------|-------------|---------|
| hybrid-rag-infra | `infra-v{major}.{minor}.{patch}` | `infra-v1.0.0` |
| hybrid-rag-inference | `inf-v*` | `inf-v1.0.0` |
| hybrid-rag-observability | `obs-v*` | `obs-v1.0.0` |
| hybrid-rag-ingest | `ingest-v*` | `ingest-v1.0.0` |
| hybrid-rag-query | `query-v*` or `rag-v*` | `rag-v1.0.0` |

**Compatibility matrix (initial):**

| Platform | infra | inference | observability | ingest | query | Notes |
|----------|-------|-----------|---------------|--------|-------|-------|
| rag-v1.0 | infra-v1.0 | inf-v1.0 | obs-v1.0 | ingest-v1.0 | query-v1.0 | `index_schema_version=1` |
| rag-v1.0 | infra-v1.1 | inf-v1.0 | obs-v1.0+ | ingest-v1.0 | query-v1.0 | infra adds Keycloak — no schema break |
| rag-v1.1 | infra-v1.0+ | inf-v1.0+ | obs-v1.1 | ingest-v1.1 | query-v1.1 | `index_schema_version=2` — full reindex required |

Breaking changes: `index_schema_version` bump, MCP SSE event shape change, removed MCP tool — require coordinated release notes in all affected sub-projects.

### 12.7 Packer image supply chain

Docker images are built per sub-project via [packer/README.md](./packer/README.md):

| Type | Sub-projects | Output naming |
|------|--------------|---------------|
| Custom build | query, ingest, inference (reranker) | `hybrid-rag-query`, `hybrid-rag-ingest-orchestrator`, … |
| Mirror + label | infra, observability, inference (vLLM) | `hybrid-rag-qdrant`, `hybrid-rag-keycloak`, `hybrid-rag-otel-collector`, … |

```bash
make packer-build-all IMAGE_TAG=rag-v1.0.0 REGISTRY=ghcr.io/myorg PUSH=true
```

Compose files MAY switch from `build:` to `image: hybrid-rag-query:${IMAGE_TAG}` for air-gapped or CI-promoted deploys.

**Root orchestration:** `Makefile` + `packer/build-all.sh` + `packer/versions.pkrvars.hcl.example` — field glossary in E-04.

### 12.8 Shipped operational artifacts (inventory)

Artifacts that exist on disk and **SHOULD** be referenced in runbooks (see also §1.4):

| Artifact | Sub-project | Purpose |
|----------|-------------|---------|
| `infra/scripts/init-db.sh` | infra | Qdrant collection + sparse vector; delegates MinIO |
| `infra/scripts/init-minio.sh` | infra | Buckets `hybrid-rag`, `hybrid-rag-staging`, IAM users |
| `infra/scripts/postgres-init.sh` | infra | DB roles: `ingest_rw`, `query_ro`, `query_session_rw`, `query_token_rw`, Keycloak DB |
| `infra/scripts/healthcheck.sh`, `backup.sh` | infra | Ops validation and backup |
| `infra/scripts/render_caddyfile.py` | infra | Templated Caddy edge config |
| `infra/keycloak/hybrid-rag-realm.json` | infra | Dev realm import (E-01 partial) |
| `observability/dashboards/langfuse-hybrid-rag.json` | observability | Pre-built Langfuse dashboard |
| `observability/dashboards/signoz-query-latency.json` | observability | SigNoz query SLO dashboard §10.5.5 |
| `observability/dashboards/signoz-ingest-throughput.json` | observability | SigNoz ingest ops dashboard §10.5.5 |
| `observability/collector/otel-collector-config.signoz.yaml` | observability | Jaeger + SigNoz fan-out overlay §10.5.2 |
| `observability/alerts/signoz-rules.yaml` | observability | SigNoz alert rules §10.5.6 |
| `observability/scripts/synthetic_trace.{py,sh}` | observability | Synthetic trace validation (bootstrap step 8) |
| `query/benchmarks/k6/research_stream.js` | query | Load test script (TL-09) |
| `query/benchmarks/locust/locustfile.py` | query | Python load alternative |
| `query/benchmarks/golden_set.json.example` | query | Ragas eval dataset template |
| `inference/reranker/sidecar.py` | inference | Working CrossEncoder HTTP sidecar |
| `ingest/requirements-docling.txt` | ingest | Optional Docling parser deps (TL-10) |
| `ingest/migrations/001_catalog_v1.sql` | ingest | Catalog DDL §4.4.1 |
| `ingest/migrations/002_conversation_sessions_v1.sql` | ingest | Conversation sessions §4.4.2 |
| `ingest/migrations/003_mcp_access_tokens_v1.sql` | ingest | MCP token RBAC §4.4.3 |
| `ingest/migrations/004_grant_query_roles_v1.sql` | ingest | Query role table grants |
| `ingest/docs/MIGRATIONS.md` | ingest | Migration runner §4.4.4 |
| `query/docs/RBAC.md` | query | MCP RBAC §7.13 |
| `query/docs/TOKEN_ADMIN.md` | query | Token admin API §7.13.10 |
| `query/docs/SESSIONS.md` | query | MCP sessions §7.11 |
| `.gitignore` | platform | Secrets, local configs, token files |
| `modules/schemas/*.json` | kernel | JSON Schema contracts §4.7 |
| `pyproject.toml`, `Makefile` (root) | platform | Lint, bootstrap, health §12.9 |

### 12.9 Root Makefile (operations)

Normative developer/CI entry points — [`Makefile`](./Makefile):

| Target | Spec § | Purpose |
|--------|--------|---------|
| `make help` | — | List all targets |
| `make env` | 12.5 | Copy `.env.example` → `.env` |
| `make bootstrap` | 12.5 | Full stack bootstrap |
| `make health` | 12.5.1 | All-plane health gates |
| `make lint` / `make format` | 23.6 | Ruff + Black |
| `make test` | 19 | pytest when `tests/` exists |
| `make packer-build-all` | 12.7 | Image supply chain |

Variables: `INFERENCE_PROFILE`, `INFRA_EDGE`, `IMAGE_TAG`, `OBS_PROFILE` (`signoz` | `metrics`).

### Production

- Single-node: systemd + compose + Caddy
- GPU enterprise: SGLang multi-model + Langfuse + SigNoz
- Future K8s: stateless MCP gateway HPA, Celery workers, managed stores

### 12.1 Hardware profile tuning matrix

Profiles apply model names, recall pools, concurrency, **and context/memory defaults** atomically via `[models].profile`:

| Profile | LLM | Recall pool | Celery × embed | Reranker | `num_ctx` | Host RAM |
|---------|-----|-------------|----------------|----------|-----------|----------|
| `mac_8gb` | `gemma2:9b` | `final=12, broad=25` | `2×1` | fast only | 8192 | 8 GB |
| `lima_12gb` | `llama3.2:3b` | `final=12, broad=25` | `2×2` | MiniLM | 8192 | 12 GB |
| `gpu_24gb` | `qwen3-coder:32b` | `final=25, broad=50` | `4×4` | BGE-large | 16384 | 32 GB |
| `a100_80gb` | `Llama-3.3-70B` (SGLang) | `final=25, broad=50` | `6×4` | BGE-large + sidecar | 32768 | 128 GB |

Apply profile: `make apply-profile PROFILE=gpu_24gb` or set `[models].profile` in TOML.

### 12.2 Neo4j JVM sizing

| Deployment | `heap_max` | `pagecache` | When to raise |
|------------|------------|-------------|---------------|
| Dev | 2G | 512m | Default compose |
| Prod single-node | 4G | 2G | >1M graph nodes |
| Large corpus | 8G | 4G | Fulltext + deep hierarchy |

Raise container/VM RAM before increasing heap. OOM during ingest → increase Podman/VM memory first.

### 12.3 Qdrant resource guidance

| Chunks | RAM estimate | Required settings |
|--------|--------------|-------------------|
| < 100k | 4–8 GB | Default HNSW |
| 100k–1M | 8–16 GB | `on_disk_payload=true` |
| 1M–5M | 16–32 GB | + INT8 quantization |
| > 5M | 32+ GB or Qdrant cluster | `hnsw_m=32`, `search_ef=256`, shard by tenant (future) |

**RAM formula (estimate):** `vectors_gb ≈ (chunk_count × embed_dimension × 4 bytes) / 1e9` (dense only) + payload on disk + HNSW graph overhead (~20–40% of vector size).

### 12.4 Horizontal scaling (normative)

| Component | Scale pattern | HPA / autoscale signal | Notes |
|-----------|---------------|------------------------|-------|
| **hybrid-rag-query** | Stateless replicas | CPU > 60% OR `rag_ttft_ms` p95 > 1.5s for 5m | Min 2 replicas prod; `warmup_clients()` each pod |
| **Celery workers** | Queue depth | KEDA on `celery_queue_depth` > 100 | Cap by embed GPU throughput |
| **Inference chat** | Dedicated GPU pool | `vllm_queue_depth`, GPU util > 80% | Never colocate ingest VLM with chat on same GPU |
| **Inference embed** | Separate port :8001 | Embed latency p95 > 100ms | Ingest and query share; throttle ingest first |
| **Qdrant** | Read replicas (search) | Search QPS > 500/s per node | Writes still single leader; INF-P6 |
| **Redis** | Sentinel or cluster | Memory > 80% OR broker lag | Separate broker from cache tier in prod |
| **Postgres** | Read replica for catalog | RO query load | `query_ro` → replica DSN optional |
| **MinIO** | Erasure coding / replication | Egress bandwidth | CDN for presigned thumbnails (optional) |

**Co-location:** Query replicas SHOULD run in same AZ as Qdrant/Neo4j for < 2ms RTT.

**Anti-pattern:** Scaling query replicas without scaling inference or Qdrant — increases admission rejections, not throughput.

**Future (E-24):** Multi-region read path with catalog replication lag SLO < 30s. Playbook: [`docs/MULTI_REGION.md`](./docs/MULTI_REGION.md).

### 12.8 Capacity planning worksheet

Use before production cutover. Replace variables with tenant forecasts.

| Input | Formula / lookup | Example (500k chunks, 20 QPS) |
|-------|------------------|--------------------------------|
| Chunk count | `N` | 500,000 |
| Qdrant RAM (dense) | `N × dim × 4B × 1.3` | ~1.6 GB vectors + payload on disk |
| Neo4j heap | `max(2G, N/250k × 1G)` | 4G heap, 2G pagecache |
| Query replicas | `peak_QPS × p95_latency / 0.7` | 20 × 0.5s / 0.7 ≈ 15 → start with 3–4 + HPA |
| Celery workers | `target_ingest_cps / embed_batch_throughput` | 50 cps / 10 ≈ 5 workers |
| GPU (chat) | Model size + KV × `max_concurrent_streams` | 24GB for 3B + 8 concurrent |
| Redis | `cache_entries × avg_result_kb + broker overhead` | 256mb–1gb dev; 2gb+ prod |
| Postgres | `tenants × collections × 50MB catalog` | 16GB disk starter |

**Headroom rule (NFR-17):** Plan for **30%** spare capacity on GPU and Qdrant RAM at peak — not 100% utilization.

**Validation:** Run §13.1 soak at planned peak QPS before go-live.

---

## 13. Evaluation

> **Harness docs:** [`query/benchmarks/README.md`](./query/benchmarks/README.md)  
> **Quality:** Ragas (§13.2) · **Load:** k6 / Locust (§13.1) · **Latency:** `benchmark_rag.py` · **Graph traces:** LangSmith (TL-07)

### 13.1 Load, soak, and chaos testing (k6 / Locust)

**Normative load harness (TL-09):**

| Tool | Role | Location |
|------|------|----------|
| **[k6](https://k6.io/)** | **Primary** — SSE `/research/stream`, HTTP gates, CI-friendly exit codes | `query/benchmarks/k6/` |
| **[Locust](https://locust.io/)** | **Alternative** — Python-native; same scenarios when k6 unavailable | `query/benchmarks/locust/` |
| `load_test.py` | Wrapper — invokes k6 or Locust, parses p95, compares NFR-23 | `query/benchmarks/` |

**k6 example** (`query/benchmarks/k6/research_stream.js`):

```javascript
import http from 'k6/http';
import { check } from 'k6';
export const options = { vus: 50, duration: '30m', thresholds: { http_req_failed: ['rate<0.001'] } };
export default function () {
  const res = http.post(`${__ENV.QUERY_URL}/research/stream`, JSON.stringify({
    query: 'What is the API rate limit?', tenant_id: 'acme-corp', collection_id: 'payments-api'
  }), { headers: { 'Content-Type': 'application/json' }, timeout: '120s' });
  check(res, { 'status 200': (r) => r.status === 200 });
}
```

**Locust:** equivalent `HttpUser` posting to `/research/stream` with `stream=True` — see `locust/locustfile.py.example`.

**Invocation:**

```bash
# k6 (primary)
k6 run -e QUERY_URL=http://localhost:8010 query/benchmarks/k6/research_stream.js

# Locust (alternative)
locust -f query/benchmarks/locust/locustfile.py --headless -u 50 -r 5 -t 30m --host http://localhost:8010

# Wrapper (either backend)
python query/benchmarks/load_test.py --backend k6 --concurrency 50 --duration 30m
python query/benchmarks/load_test.py --backend locust --concurrency 50 --duration 30m
```

**Load test** (pre-release, target hardware profile):

| Scenario | Concurrency | Duration | Pass criteria |
|----------|-------------|----------|---------------|
| Scoped FAQ | 50 SSE streams | 30 min | p95 TTFT < 2s; error < 0.1% |
| Unscoped research | 20 streams | 15 min | p95 total < 20s; scope accuracy ≥ baseline |
| Burst admission | 0 → 100 QPS in 10s | 5 min | 429 rate < 5%; no 5xx |
| Cache-heavy | 50 identical queries | 10 min | cache hit ≥ 80%; p95 < 100ms |

**Soak test (NFR-23):** 2 hours at 50 concurrent scoped streams — p95 drift < 15% vs first 15 min; no memory growth > 10% on query pods.

**Chaos scenarios** (staging, monthly):

| Injection | Expected behavior |
|-----------|-------------------|
| Redis unavailable 60s | Rate limit fails open with alert; cache miss only |
| Embed timeout | L3 degrade — abstain or cache |
| Qdrant slow (+500ms) | L1 skip graph; alert `qdrant_search_latency_ms` |
| vLLM OOM restart | Circuit open → 503 until health recovers; no retry storm |
| Ingest flood | Auto-pause enqueue (FR-29); query TTFT within NFR-18 |

### 13.2 RAG quality evaluation (Ragas)

**Normative quality harness (TL-08):** **[Ragas](https://docs.ragas.io/)** computes faithfulness, answer relevancy, and context recall on golden-set runs. Invoked from `benchmark_rag.py --ragas` on nightly live CI.

| Ragas metric | Platform gate | Maps to |
|--------------|---------------|---------|
| `faithfulness` | mean ≥ **0.85** | Grounding — answer supported by retrieved context |
| `answer_relevancy` | mean ≥ **0.80** | Question ↔ answer alignment |
| `context_recall` | mean ≥ **0.75** | Retrieved context covers `ground_truth` |

**Dataset:** golden set JSON (below) loaded via `datasets` or `query/benchmarks/golden_set.json`.

**Eval flow:**

```mermaid
flowchart LR
    GS[golden_set.json] --> RUN[run_rag_pipeline per row]
    RUN --> COLLECT[question, contexts, answer, ground_truth]
    COLLECT --> RAGAS[ragas.evaluate]
    RAGAS --> OUT[benchmarks/last_ragas.json]
    OUT --> GATE[compare faithfulness / relevancy gates]
```

**Dependencies:** `query/benchmarks/requirements.txt` — `ragas`, `datasets`, `langchain-openai` or OpenAI-compatible client pointed at inference `vllm_url`.

**Complements LangSmith:** Ragas = release quality gates; LangSmith = per-node trace regression (LG-4). Langfuse = prod cost/sessions only.

```bash
pip install -r query/benchmarks/requirements.txt
python query/benchmarks/benchmark_rag.py --limit 50 --ragas --fail-faithfulness 0.85
```

#### 13.2.1 `benchmark_rag.py` CLI (normative)

**Path:** `query/benchmarks/benchmark_rag.py` (implementation required LG-4).  
**Invokes:** `run_rag_pipeline()` per golden-set row; optional Ragas evaluation.

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--golden-set` | path | `benchmarks/golden_set.json` | Input dataset |
| `--limit` | int | all | Max rows to run |
| `--ragas` | bool | false | Run Ragas metrics (TL-08) |
| `--write-baseline` | bool | false | Write `benchmarks/baselines.json` |
| `--output` | path | `benchmarks/last_run.json` | Latency output |
| `--ragas-output` | path | `benchmarks/last_ragas.json` | Ragas output |
| `--fail-faithfulness` | float | — | Exit non-zero if mean below |
| `--fail-answer-relevancy` | float | — | Exit non-zero if mean below |
| `--fail-context-recall` | float | — | Exit non-zero if mean below |
| `--fail-total-p95-ms` | int | — | Exit non-zero if p95 above |
| `--warn-total-p95-ms` | int | — | Warn only |
| `--compare-otel` | bool | false | Measure OTel overhead (OBS-P3) |
| `--live-stack` | bool | false | Require live stores (implicit on CI nightly) |

**Output `last_run.json` shape (normative):**

```json
{
  "run_at": "2026-07-09T22:00:00Z",
  "count": 20,
  "stages_ms": {
    "embed": { "p50": 42, "p95": 88 },
    "retrieve": { "p50": 95, "p95": 210 },
    "total": { "p50": 3200, "p95": 8900 }
  },
  "scope_accuracy": 0.92,
  "abstain_rate": 0.05
}
```

### 13.3 Golden set entry

```json
{
  "id": "pay-001",
  "question": "How do I rotate API keys?",
  "ground_truth": "API keys are rotated from the admin console under Settings → Security.",
  "tenant_id": "acme-corp",
  "collection_id": "payments-api",
  "expect_document_id": "admin-guide"
}
```

### Metrics & gates

| Gate | Metric | Tool | Default threshold |
|------|--------|------|-------------------|
| Ragas faithfulness | mean | **Ragas** | ≥ 0.85 |
| Ragas answer relevancy | mean | **Ragas** | ≥ 0.80 |
| Ragas context recall | mean | **Ragas** | ≥ 0.75 |
| Scope accuracy | % correct `expect_document_id` | ≥ 90% |
| Abstention precision | no false answers on low-score set | ≥ 95% |
| P95 query latency | end-to-end | < baseline × 1.1 vs `benchmarks/baselines.json` |
| P95 retrieval-only | excl. LLM | < baseline × 1.25 |
| P95 TTFT | first SSE token | < baseline × 1.1 |
| Ingest throughput | chunks/s | ≥ baseline × 0.9 |
| MCP contract | parser tests | 100% pass |
| Soak stability | 2h / 50 streams | NFR-23 |
| Chaos suite | staging monthly | All scenarios pass |
| OTel overhead | `--compare-otel` | < 5% p95 regression |
| Mock ingest floor | chunks/min | ≥ 1000 (CI mock, no inference) |
| Live ingest floor | chunks/min | ≥ 2.0 (real embed, CI live stack) |

**Benchmark harness:**

| Script | Purpose | CI tier |
|--------|---------|---------|
| `benchmark_rag.py` | Golden questions → per-stage p50/p95; `--ragas` quality | Nightly live |
| `benchmark_ingest.py --mock` | Synthetic chunks → chunks/min | Every PR |
| `benchmark_ingest.py` | Real embed throughput | Nightly live |
| `load_test.py` | k6 or Locust soak wrapper | Pre-release |
| `k6/research_stream.js` | Direct k6 SSE load | Pre-release / staging |
| `locust/locustfile.py` | Direct Locust SSE load | Pre-release / staging |
| `smoke_test.py --e2e` | End-to-end timing + JSON telemetry | Nightly |
| `compare_benchmark_run.py` | Regression vs `last_run.json` | Nightly |

```bash
# Advisory (non-blocking)
benchmark_rag.py --limit 4 --warn-total-p95-ms 45000
benchmark_rag.py --limit 10 --ragas --warn-faithfulness 0.80
benchmark_ingest.py --mock --warn-chunks-per-min 1000
load_test.py --backend k6 --concurrency 50 --duration 30m --dry-run

# Enforced (live-gates, exit 2 on fail)
benchmark_rag.py --limit 2 --fail-total-p95-ms 120000 --ragas --fail-faithfulness 0.85
benchmark_ingest.py --chunks 8 --fail-chunks-per-min 2.0
load_test.py --backend k6 --concurrency 50 --duration 2h   # NFR-23 soak
```

**Regression ratios** (`benchmarks/baselines.json`):

| Metric | Rule |
|--------|------|
| Mock ingest | current ≥ 80% of baseline |
| Live RAG p95 | current ≤ 125% of baseline |
| Scope accuracy | current ≥ baseline |

**CI tiers:**

- **Unit gates** — every PR: pipeline mocks, MCP markdown contract, SSE event contract
- **Live gates** — nightly (`LIVE_STACK=1`): scope accuracy, Ragas, ingest throughput on real stores

**Evaluation paths:** Direct `run_rag_pipeline()` for RAG regression; BFF harness for end-user path parity (recommended before release).

### 13.4 Test-driven development (TDD)

Normative methodology: **[docs/TESTING.md](./docs/TESTING.md)** · **TL-11** · **G13** · **FR-33/34**

```mermaid
flowchart LR
    RED["Red<br/>failing test"] --> GREEN["Green<br/>min impl"]
    GREEN --> REF["Refactor<br/>keep green"]
```

| Practice | Requirement |
|----------|-------------|
| **Contracts first** | Chunk schema, MCP markdown order, SSE events — test before handler code |
| **Frozen fixtures** | Breaking UI/BFF changes require explicit fixture updates in same PR |
| **Mocked unit tests** | LangGraph nodes, parsers, scope logic — no live GPU in unit tier |
| **Integration last** | `LIVE_STACK=1` after unit + contract green |
| **Perf as tests** | `baselines.json` + Ragas gates — same red/green discipline (FR-16) |

**PR gate:** `pytest tests/unit tests/contract` MUST pass in query and ingest before merge.

**Release gate:** integration + Ragas + baseline ratios — §13 metrics table.

---

## 14. Implementation phases

| Phase | Module | Deliverable |
|-------|--------|-------------|
| **P0** | all sub-projects + kernel | `infra-v1.0` + `ingest-v1.0` + `query-v1.0`; shared schema; contract tests; `research_documents` |
| **P0.5** | query | `POST /research/stream` + contract tests |
| **P1** | ingest + query | Catalog ACL; scope bar UI |
| **P1.5** | infra + inference + observability + query | `infra-v1.0` + `inf-v1.0` + `obs-v1.0`; OTel/Jaeger; Keycloak realm; `rag_stage_ms` logs |
| **P1.6** | platform | Packer images; bootstrap runbook; compatibility matrix (spec v0.12) |
| **P1.7** | query + ingest + platform | Performance guide; `baselines.json`; two-stage rerank (v0.13) |
| **P1.8** | platform + infra + observability | Implementation stack §1.3; infra/obs performance plans (v0.14) |
| **P1.9** | query + ingest + inference | LangGraph production nodes; sub-project performance docs (v0.16) |
| **P2** | platform | SLI dashboards; chaos suite; tenant quotas enforcement |
| **P2.5** | query | Two-stage rerank + query cache |
| **P2.6** | query + ingest | Benchmark harness + CI regression gates |
| **P3** | query + infra | Multi-tenant hardening; OIDC JWT on MCP (FR-23) |
| **P4** | infra + query | K8s Helm; MCP HPA; retention job |
| **P5** | ingest + query | Cross-collection queries; federation |

---

## 15. API examples

### MCP

```json
{
  "name": "research_documents",
  "arguments": {
    "query": "What is the rate limit for the payments API?",
    "tenant_id": "acme-corp",
    "collection_id": "payments-api"
  }
}
```

### HTTP stream

```bash
curl -N -X POST http://127.0.0.1:8010/research/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"Summarize the refund policy","tenant_id":"acme-corp","collection_id":"hr-policies"}'
```

---

## 16. Glossary

| Term | Definition |
|------|------------|
| **Hybrid RAG** | Dense + sparse retrieval fused before reranking |
| **Scope** | Resolved document set filter |
| **Collection** | Named corpus of related documents |
| **MCP** | Model Context Protocol — agent tool surface |
| **Abstention** | Refusal when retrieval confidence is low |
| **RRF** | Reciprocal Rank Fusion — merges ranked lists from dense, sparse, and fulltext recall |
| **TTFT** | Time to first token — first SSE `token` event |
| **Warmup** | Preloading store clients and models at MCP startup |
| **Sidecar** | HTTP service hosting reranker model separately from MCP workers |
| **Backpressure** | Ingest throttle signal when Celery queue depth exceeds threshold |
| **HNSW** | Hierarchical Navigable Small World — Qdrant approximate nearest-neighbor index |
| **KV cache** | GPU memory holding attention key/value tensors for active LLM sequences |
| **num_ctx** | Maximum context window (tokens) the inference server allocates per request |
| **Principal** | Identity subject for ACL — `user:{sub}` from JWT |
| **OIDC** | OpenID Connect — auth protocol; Keycloak is the default issuer |
| **JWKS** | JSON Web Key Set — public keys for JWT signature verification |
| **Token budget** | Pre-LLM accounting ensuring prompt + completion fit within `num_ctx` |

---

## 17. Architecture decisions

| ID | Question | Decision | Rationale |
|----|----------|----------|-----------|
| OD1 | Global Qdrant collection vs per-tenant | **Global + `tenant_id` index** | Simpler ops; per-tenant collections for regulated tier only |
| OD2 | Version retention policy | **Last 3 versions per document** | Balances rollback vs storage; nightly prune job |
| OD3 | Cross-collection queries in v1 | **Deferred to P5** | v1 scopes to one collection (+ `additional_collections` admin flag) |
| OD4 | Per-collection embedding models | **Single embed model per deployment in v1** | Avoids dimension mismatch; collection override in v2 |
| OD5 | Bearer auth on MCP `/sse` | **Config-driven; required in prod MT** | Dev friction vs security trade-off |
| OD6 | Monolith vs split deploy | **Split by default in prod** | `hybrid-rag-query` and `hybrid-rag-ingest` separate images; compose for dev |
| OD7 | Event bus for cache invalidation | **Redis Streams `rag:events`** | Loose coupling ingest → query; optional webhook adapter |
| OD8 | Observability split | **Langfuse (LLM) + OTel/Jaeger (distributed)** in `observability/` | Single sub-project compose; SDK-only in apps |
| OD9 | MCP auth model | **MCP access token (`rag_mcp_*`) + optional JWT bridge** | Token carries RBAC; fits MCP hosts |
| OD10 | Identity hosting | **Keycloak in `hybrid-rag-infra`** | Same Postgres host, separate DB; realm import for dev |
| OD11 | Image releases | **Packer per sub-project + compatibility matrix** | Independent version trains with contract gates |

### 17.1 Remaining open questions

| ID | Question | Notes |
|----|----------|-------|
| OQ1 | Managed vs self-hosted Qdrant/Neo4j for enterprise tier | Affects Helm values and backup strategy |
| OQ2 | Embedding model swap without full reindex | Requires dimension migration playbook |
| OQ3 | Federated search across multiple MCP server instances | Multi-region catalog federation |
| OQ4 | Keycloak vs external IdP (Azure AD, Okta) | Federation via OIDC same claim contract |
| OQ5 | Query JWT validation: inline vs auth sidecar | Default inline JWKS in query process |

---

## 18. Performance engineering

> **Split by sub-project:** Query → [`query/`](./query/). Ingest → [`ingest/`](./ingest/). Stores → [`infra/`](./infra/). Inference → [`inference/`](./inference/). Metrics → [`observability/`](./observability/).

### 18.1 Critical path

```mermaid
flowchart LR
    A[Request] --> B{Cache hit?}
    B -->|yes| Z[Return cached]
    B -->|no| C{Explicit scope?}
    C -->|yes| E[Embed]
    C -->|no| D[Supervisor]
    D --> E
    E --> F[Hybrid retrieve]
    F --> G[Rerank]
    G --> H[Graph enrich]
    H --> I[Stream answer]
```

**Design rule:** Every box except Embed and Retrieve MUST be optional via config or request pins.

### 18.2 Caching layers

| Layer | Key | TTL | Invalidation |
|-------|-----|-----|--------------|
| Query result | `sha256(scope + query + config_version)` | 3600s | `bump_cache_version()` on ingest complete |
| Chunk dedup | `content_hash` | Permanent | N/A |
| File registry | `path + hash` | Permanent | Updated on connector sync |
| Catalog ACL | In-process LRU | 60s | On `acl.changed` audit event |
| MCP SSE connection | Per server id | 10 min idle | Multiplexer prunes |
| Embed vector | `sha256(normalized_query_text)` | 86400s | Optional; invalidate on embed model change |
| Semantic near-dup | `embedcache:` + cosine > 0.98 | 3600s | Optional; reduces embed calls for FAQ variants |

### 18.3 Inference plane performance

| Provider | TTFT strategy | Embed strategy |
|----------|---------------|----------------|
| Ollama | `keep_alive=30m`; preload at warmup | Batch `embed(input=[...])` |
| vLLM | Continuous batching; dedicated embed port | Separate `vllm_embed_url` |
| SGLang | RadixAttention; multi-model on A100 | Colocated or dedicated embed server |

**Reranker sidecar:** Run CrossEncoder as HTTP service (`POST /predict`) when multiple MCP workers would each load ~1 GB model weights. Dual sidecar (fast + full) uses ~2 GB total — size host accordingly.

### 18.4 Ingest vs query resource isolation

| Resource | Ingest priority | Query priority | Conflict resolution |
|----------|-----------------|----------------|---------------------|
| GPU | Embed + VLM batches | LLM + embed + rerank | Separate vLLM ports; throttle `celery_concurrency` during peak query hours |
| CPU | Parse pool | Reranker (if local) | Sidecar reranker on GPU |
| Qdrant | Bulk upsert | Low-latency search | Upsert off-peak; `wait=false` on bulk writes |
| Neo4j | UNWIND batch writes | Read-only graph enrich | Write during ingest windows |

**Recommended:** Schedule full reindex jobs off-peak; incremental sync during business hours with rate limit (`ingest_max_chunks_per_minute`).

### 18.5 Performance observability

**Required metrics (SigNoz/Prometheus):**

| Metric | Type | Alert threshold |
|--------|------|-----------------|
| `rag_stage_ms.{stage}` | Histogram | p95 > budget × 1.5 for 5 min |
| `rag_ttft_ms` | Histogram | p95 > 2s |
| `ingest_chunks_per_second` | Gauge | < 50% baseline for 10 min |
| `celery_queue_depth` | Gauge | > 500 for 5 min |
| `query_cache_hit_rate` | Counter ratio | < 5% when enabled (informational) |
| `qdrant_search_latency_ms` | Histogram | p95 > 200ms |
| `inference_cold_start_total` | Counter | > 0 in prod (should be zero after warmup) |

**Langfuse:** Record `timings_ms` as span attributes; skip `answer` generation span on cache hit.

### 18.6 Performance troubleshooting guide

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| High TTFT, low `retrieve` | Cold inference model | `warmup_clients()`, `keep_alive`, vLLM always-on |
| High `retrieve` only | Corpus growth / low `search_ef` | Raise `search_ef`; enable quantization; narrow scope |
| High `rerank` | Large recall pool | Enable two-stage; reduce `final_recall_limit` |
| High `supervisor` | Unscoped queries | Pin scope in UI; `skip_supervisor_when_explicit` |
| Slow ingest | Embed bottleneck | Raise `embed_parallelism`; batch embed API; more Celery workers |
| Neo4j OOM | Heap too small | Increase VM RAM + JVM heap |
| Qdrant RAM growth | Payload in memory | `on_disk_payload=true`; INT8 quantization |
| Context overflow / garbled answers | `num_ctx` too small or no truncation | Raise `num_ctx`; lower `max_context_tokens`; enable truncation policy |
| OOM during answer | KV cache + large `num_ctx` + concurrent streams | Lower `max-num-seqs`; reduce `num_ctx`; limit concurrent streams |
| Slow answers, high `context_tokens` | Too much context sent to LLM | Reduce `rerank_top_k`; truncate tables; strip lineage |
| macOS swap thrashing | Multiple Ollama models loaded | One model at a time; shorter `keep_alive`; sidecar reranker |
| First query slow only | Cold clients | `warmup_on_startup=true` |
| BFF slow, RAG fast | Cold SSE connection | MCP multiplexer pool reuse |

### 18.7 Performance acceptance checklist (release gate)

- [ ] `benchmark_rag.py` p95 within baseline × 1.1 on golden set
- [ ] `benchmark_ingest.py --mock` ≥ 1000 chunks/min
- [ ] Live ingest ≥ 50 chunks/s on target hardware profile
- [ ] TTFT p95 < 2s on GPU with scoped query
- [ ] Retrieval-only p95 < 500ms (excl. supervisor + LLM)
- [ ] No regression in scope accuracy vs prior release
- [ ] `warmup_clients()` completes < 30s
- [ ] Query cache invalidation verified after ingest
- [ ] `context_tokens` ≤ `max_context_tokens` on 100% of golden-set queries
- [ ] No OOM under soak test (50 concurrent queries, target profile)
- [ ] GPU VRAM < 90% at P95 concurrent load

### 18.8 Memory and context quick reference

```mermaid
flowchart TB
    subgraph Host["Host memory"]
        MCP[MCP ~500MB]
        CEL[Celery ×N]
        QD[Qdrant RAM]
        N4J[Neo4j JVM]
    end
    subgraph GPU["GPU VRAM"]
        LLM[LLM weights + KV cache]
        EMB[Embed model]
        RER[Reranker sidecar]
    end
    subgraph Context["Per-query context (CPU RAM, transient)"]
        BLK[4 context blocks ≤12k tokens]
        PRM[System prompt + query]
    end
    BLK --> LLM
    PRM --> LLM
```

**Sizing checklist:**

1. Pick hardware profile → sets `num_ctx`, `max_context_tokens`, model sizes
2. Size Qdrant RAM from chunk count (§12.3 formula)
3. Size Neo4j heap from node count (§12.2)
4. Reserve VRAM: LLM + embed port + headroom (§6.14.2)
5. Verify token budget: `max_context_tokens + max_answer_tokens + margin < num_ctx`
6. Load test with `context_tokens` telemetry — no truncation on golden set unless expected

### 18.9 Optimization hierarchy

Apply tuning in order (detail: [`docs/PERFORMANCE.md`](./docs/PERFORMANCE.md)):

1. **Correctness** — scope pins, ACL, token budget
2. **Critical path** — skip supervisor, two-stage rerank, disable graph when not needed
3. **Warmth** — `warmup_clients()`, vLLM always-on, MCP SSE pool
4. **Batching** — ingest embed batches, Qdrant upsert batches
5. **Caching** — query result cache, ACL LRU, dedup skip
6. **Store tuning** — `search_ef`, `on_disk_payload`, Neo4j heap
7. **Scale-out** — workers, replicas, sharding

### 18.10 Profile optimization presets

Atomic config via `[models].profile`. Key deltas:

| Profile | Query focus | Ingest focus | TTFT target |
|---------|-------------|--------------|-------------|
| `mac_8gb` | `final_recall_limit=12`, graph off | `celery×1`, defer VLM | Best-effort |
| `lima_12gb` | graph off, fast reranker only | `2×1` embed | P95 < 45s (NFR-03) |
| `gpu_24gb` | two-stage rerank, dense scope | `4×4`, off-peak bulk | P95 TTFT < 2s (NFR-02) |
| `a100_80gb` | `max_context_tokens=24000`, parallel scope | `6×4`, SGLang LLM | P95 TTFT < 1.5s |

**Prod rule (NFR-18):** schedule full reindex 22:00–06:00 local when query and ingest share embed GPU `:8001`.

### 18.11 Store and connection tuning

| Store | Query optimization | Ingest optimization |
|-------|-------------------|---------------------|
| **Qdrant** | `search_ef` 128–256 by corpus size; filter `tenant_id`+`collection_id`; gRPC client | `qdrant_upsert_batch=100`; `wait=false` bulk; off-peak writes |
| **Neo4j** | Read-only sessions; graph enrich limited to `rerank_top_k` ids | `neo4j_unwind_batch=50`; no per-node MERGE loops |
| **Redis** | Result cache DB 0 with LRU; ACL LRU 60s in-process | Dedup MGET batches; broker DB 1 never evicted |
| **Postgres** | RO pool `5+10`; batch catalog lookups | RW pool; index `(tenant_id, collection_id)` |

**Qdrant at scale:** `on_disk_payload=true` required > 100k chunks; INT8 quantization recommended > 500k. See [`infra/docs/QDRANT.md`](./infra/docs/QDRANT.md).

### 18.12 Performance anti-patterns

| Anti-pattern | Impact | Remediation |
|--------------|--------|-------------|
| Cross-encoder scope on all queries | +200–400ms | `scope_rerank_mode=dense`; UI scope pins |
| `final_recall_limit=50` without two-stage rerank | Rerank P95 > 800ms | Enable `reranker_fast` or lower limit |
| Peak ingest + peak query on same embed GPU | TTFT spikes > 20% | Off-peak ingest; throttle `celery_concurrency` |
| Per-request store client creation | +50–200ms first op | `warmup_clients()` + pooled clients (FR-25) |
| Query cache without `cache_bump` | Stale answers post-ingest | Subscribe IF-3 `ingest.completed` |
| `num_ctx` raised without `max_context_tokens` trim | KV OOM | Maintain ≥ 512 token margin (§6.13) |

### 18.13 Benchmark baselines

Committed per hardware profile in `query/benchmarks/baselines.json` (see `.example`). CI compares nightly runs via `compare_benchmark_run.py` — regression ratios in §13.

### 18.14 SLIs, SLOs, and error budgets

| SLI | Measurement | SLO (standard tier) | Error budget (30d) |
|-----|-------------|---------------------|-------------------|
| Availability | `/healthz` 200 AND `research_ready=true` | 99.9% | 43.2 min downtime |
| Query success | HTTP 200/SSE `done` without `error` | 99.5% | 3.6h failed queries |
| TTFT | First SSE `token` latency | p95 < 2s | Burn alert if p95 > 2s for 1h |
| Retrieval | `retrieve` stage only | p95 < 500ms | Burn alert × 1.5 for 30m |
| Ingest freshness | `ingest.completed` → searchable | p95 < 5 min | Informational |
| Saturation | GPU util, queue depth | < 85% sustained | Scale trigger |

**Burn-rate alerts:** 2× budget consumption in 1h (page); 6× in 6h (critical).

**Dashboards:** Prometheus + Grafana or SigNoz — `observability/dashboards/` (OBS-P5).

### 18.15 Circuit breakers and bulkheads

| Client | Failure threshold | Open duration | Half-open | Fallback |
|--------|-------------------|---------------|-----------|----------|
| vLLM chat | 5 errors / 30s | 30s | 1 probe | L3 abstain message |
| vLLM embed | 5 errors / 30s | 20s | 1 probe | L4 abstain |
| Qdrant | 3 timeouts / 20s | 60s | 1 search | L4 abstain |
| Neo4j | 5 errors / 30s | 30s | 1 read | Skip graph (L1) |
| Reranker HTTP | 5 errors / 30s | 20s | 1 predict | Dense top-k (L2) |

**Library:** `httpx` + `tenacity` or dedicated breaker (e.g. `pybreaker`). **MUST NOT** retry LLM calls more than once on 5xx.

**Bulkhead:** Separate connection pools per store — embed pool size ≤ 20; Qdrant ≤ 32; Neo4j ≤ 16 per query replica.

### 18.16 Connection pool defaults (per query replica)

| Client | Pool min | Pool max | Timeout | Keep-alive |
|--------|----------|----------|---------|------------|
| Qdrant gRPC | 4 | 32 | 5s | yes |
| Neo4j Bolt | 2 | 16 | 10s | yes |
| Redis | 4 | 32 | 2s | yes |
| httpx (inference) | 8 | 40 | chat 120s, embed 30s | 30s |
| Postgres RO | 5 | 20 | 5s | yes |

Tune via `[performance]` in `query.toml`. Exhaustion → 503 with `pool_exhausted` metric — not unbounded wait.

### 18.17 Compression and payload efficiency

| Layer | Policy | When |
|-------|--------|------|
| MinIO objects | gzip for `raw/` text exports | > 64 KB |
| Qdrant vectors | INT8 quantization | > 500k chunks (INF-P1) |
| HTTP responses | gzip JSON admin APIs | ingest orchestrator |
| Chunk text in context | Truncate tables; strip boilerplate | Always before LLM |
| Presigned URLs | Short TTL (3600s default) | Reduces URL size in payloads |

**Network:** Prefer Qdrant gRPC (:6334) over REST for retrieve — ~15–30% latency reduction at scale.

---

## 19. Test-driven development (engineering)

Full playbook: **[docs/TESTING.md](./docs/TESTING.md)**

### 19.1 Scope

TDD applies to all sub-projects that ship application logic:

| Sub-project | TDD focus |
|-------------|-----------|
| `hybrid-rag-query` | LangGraph nodes, MCP tools, SSE, rate limits, cache |
| `hybrid-rag-ingest` | Parsers, chunk builder, dedup, admin API, Celery tasks |
| `mod-kernel` | Schema versioning, event shapes, compatibility matrix |
| `hybrid-rag-inference` | Health probes, reranker `/predict` contract (not vLLM upstream) |
| `hybrid-rag-observability` | Collector config validation, synthetic trace script |

Infra compose stacks use **health scripts + `compose config`** as their “tests” — not pytest.

### 19.2 Test pyramid (summary)

| Tier | Tool | PR | Nightly | Release |
|------|------|-----|---------|---------|
| Unit | pytest + mocks | ✓ | ✓ | ✓ |
| Contract | pytest + fixtures | ✓ | ✓ | ✓ |
| Integration | pytest + live stack | — | ✓ | ✓ |
| Quality | Ragas | — | ✓ | ✓ |
| Performance | baselines.json | warn | ✓ | ✓ |
| Load | k6 / Locust | — | — | ✓ |

### 19.3 Normative contract tests (kernel)

Cross-module tests in [SHARED_CONTRACTS.md](./modules/SHARED_CONTRACTS.md) §14 — **MUST exist and pass** before `rag-v1.x`:

| Test | Validates |
|------|-----------|
| `test_chunk_payload_schema.py` | Ingest output matches kernel schema |
| `test_query_reads_ingest_fixture.py` | Query reads seeded corpus |
| `test_event_cache_bump.py` | `ingest.completed` invalidates cache |
| `test_catalog_ro_role.py` | Query DSN cannot INSERT |
| `test_mcp_markdown_contract.py` | Answer + Sources + telemetry order |
| `test_sse_event_contract.py` | Allowed SSE event types only |
| `test_tenant_filter_enforced.py` | Cross-tenant retrieval impossible |

New IF or payload fields: **extend tests first** (FR-33).

### 19.4 Feature workflow (example: retrieve node)

1. Add `query/tests/unit/test_retrieve_node.py` with mocked Qdrant returning fixture points  
2. Assert `RAGState.retrieved_chunks` and `timings_ms.retrieve`  
3. Implement `node_retrieve` in `rag_graph.py` until green  
4. Add integration test with live Qdrant on nightly  
5. Update `baselines.json` if retrieve p95 budget changes intentionally  

Same pattern for parsers, MCP tools, admin routes.

### 19.5 Anti-patterns

| Anti-pattern | Remediation |
|--------------|-------------|
| Implement feature, add tests later | Reject PR without contract/unit tests (FR-34) |
| Skip tests with `@pytest.mark.skip` on contracts | Require issue link + expiry date |
| Only manual chat testing | Add golden fixture + Ragas row |
| Live GPU in unit tests | Mock inference clients; live in integration tier |
| Change MCP markdown order without fixture update | Breaks BFF — coordinate release |

### 19.6 CI integration

```yaml
# Illustrative — per sub-project Makefile / GitHub Actions
unit-contract:
  run: pytest tests/unit tests/contract -q --tb=short

nightly-live:
  needs: unit-contract
  env: LIVE_STACK=1
  run: |
    pytest tests/integration -q
    python benchmarks/benchmark_rag.py --limit 20 --ragas
    python benchmarks/compare_benchmark_run.py benchmarks/last_run.json benchmarks/baselines.json
```

---

## 21. Documentation engineering

Full playbook: **[docs/DOCUMENTATION.md](./docs/DOCUMENTATION.md)** · **G14** · **FR-35/36/37** · **NFR-25** · **TL-12/13**

Documentation is a **first-class deliverable**, not a post-release afterthought. A novice with no oral tradition MUST be able to understand purpose, boundaries, operations, and extension points from maintained guides and inline code comments.

### 21.1 Audience guides (normative map)

| Audience | Guide | Covers |
|----------|-------|--------|
| **End user** | [docs/USER_GUIDE.md](./docs/USER_GUIDE.md) | Chat and MCP usage, scope, citations, abstention, privacy |
| **Administrator** | [docs/ADMIN_GUIDE.md](./docs/ADMIN_GUIDE.md) | Collections, ingest jobs, ACL, quotas, MinIO assets |
| **Deployment / SRE** | [docs/DEPLOYMENT_GUIDE.md](./docs/DEPLOYMENT_GUIDE.md) | Bootstrap order, profiles, health gates, upgrades, capacity |
| **Solution architect** | [docs/ARCHITECT_GUIDE.md](./docs/ARCHITECT_GUIDE.md) | IF-* interfaces, data model, security, scaling, ADR index |
| **Developer** | [docs/DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md) | Onboarding, TDD, LangGraph, parsers, PR expectations |

Contributing expectations: [CONTRIBUTING.md](./CONTRIBUTING.md).

```mermaid
flowchart TB
    subgraph Platform["Platform docs/docs/"]
        DOC[DOCUMENTATION.md standards]
        UG[USER_GUIDE.md]
        AG[ADMIN_GUIDE.md]
        DG[DEPLOYMENT_GUIDE.md]
        ARG[ARCHITECT_GUIDE.md]
        DEVG[DEVELOPER_GUIDE.md]
    end

    subgraph Sub["Each sub-project"]
        RDME[README.md quick start]
        SPEC[SPEC.md normative]
        SDOC[docs/*.md topics]
    end

    DOC --> UG & AG & DG & ARG & DEVG
    DEVG --> Sub
    DG --> Sub
```

**FR-35 acceptance:** All five audience guides exist at listed paths; each of `query/`, `ingest/`, `infra/`, `inference/`, `observability/` has `README.md` + `SPEC.md`; integration topics live under `docs/` per sub-project README index.

### 21.2 Mermaid diagram policy (TL-12)

| Diagram kind | Required format | Example |
|--------------|-----------------|---------|
| Architecture / context | `flowchart` with `subgraph` | §3.1, [ARCHITECT_GUIDE.md](./docs/ARCHITECT_GUIDE.md) |
| Auth / request sequence | `sequenceDiagram` | §7.10 OIDC |
| Pipelines / eval / TDD | `flowchart LR` | §6.1, §13.2, [TESTING.md](./docs/TESTING.md) |
| Job / state lifecycle | `stateDiagram-v2` | [ADMIN_GUIDE.md](./docs/ADMIN_GUIDE.md) |

**Allowed non-Mermaid:** directory trees, CLI transcripts, JSON/YAML/TOML examples, markdown tables.

**Forbidden:** ASCII box-and-arrow diagrams in normative `*.md` under `docs/`, `*/SPEC.md`, and this platform spec.

### 21.3 Documentation freshness (NFR-25)

| Change | Minimum doc updates |
|--------|---------------------|
| MCP tool or SSE event | `query/docs/MCP.md`, contract fixtures, [USER_GUIDE.md](./docs/USER_GUIDE.md) if visible |
| Ingest stage or parser | `ingest/docs/`, [ADMIN_GUIDE.md](./docs/ADMIN_GUIDE.md) |
| Config key or env var | Sub-project `README.md`, `config/*.toml` comment, [DEPLOYMENT_GUIDE.md](./docs/DEPLOYMENT_GUIDE.md) |
| IF-* or schema field | §3.3, [SHARED_CONTRACTS.md](./modules/SHARED_CONTRACTS.md), [ARCHITECT_GUIDE.md](./docs/ARCHITECT_GUIDE.md) |
| Performance SLO | [PERFORMANCE.md](./docs/PERFORMANCE.md), `baselines.json` |

**PR gate:** Authors complete checklist in [DOCUMENTATION.md](./docs/DOCUMENTATION.md) §3.4 before merge.

### 21.4 Code comments for novices (TL-13, FR-37)

Application code MUST explain **intent** and **contracts**, not restate syntax. Full coding patterns: **§23** and [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md).

| Artifact | Requirement |
|----------|-------------|
| Python module | Top-level docstring: role + link to spec § |
| LangGraph node | Docstring: `RAGState` keys read/written, FR refs, stub notes |
| Parser / Celery task | Docstring: input artifact, output shape, idempotency key |
| TypeScript export | TSDoc with `@param` / `@returns` for BFF and UI |
| Shell init scripts | Header: purpose, env vars, idempotency |

**Stub convention:** `# Stub:` or docstring **Stub:** line naming the future module and spec section.

**Example reference implementation:** `query/app/rag_graph.py`, `query/app/rag_state.py`.

### 21.5 Documentation CI (recommended)

| Check | Blocks |
|-------|--------|
| Link check on `docs/*.md` | Broken audience cross-links |
| Mermaid lint (optional) | Invalid diagram syntax on PR |
| `pytest` + contract tests | Code without tests (§19) |
| Doc path grep for box-drawing chars in flow sections | ASCII diagram regression |

---

## 22. Summary: what to spec next (v0.28 candidates)

> **Shipped v0.23–v0.29:** … **auth + MCP handlers + LG-1–LG-4 + JWKS/stdio** (v0.28) · **Neo4j graph enrich** (v0.29). **Next:** catalog MCP tools, circuit breakers, prod health gates toward **rag-v1.0**.

Living detail: [docs/SPEC_ROADMAP.md](./docs/SPEC_ROADMAP.md). **On-disk status:** §1.4.

```mermaid
flowchart TB
    subgraph shipped["Shipped v0.23–v0.27"]
        SIGNOZ[SigNoz §10.5]
        SESS[MCP sessions §7.11]
        RBAC[Token RBAC §7.13]
        HYGIENE[v0.27 normative gaps]
    end

    subgraph v028["v0.28 implement next"]
        AUTH[auth.py token_store.py rbac.py]
        HANDLERS[MCP tool handlers]
        STORE[session_store.py]
        TESTS[contract tests]
        MIGRATE[migrate.py]
    end

    subgraph v030["rag-v1.0 bundle"]
        LG[LG-1–LG-6 production path]
        BENCH[benchmark_rag.py]
        PROD[prod OTel + health gates]
    end

    shipped --> AUTH
    AUTH --> HANDLERS --> STORE --> TESTS
    TESTS --> LG --> BENCH --> PROD
    HYGIENE --> MIGRATE
```

### 22.1 Implementation status (rag-v1.0 — 2026-07-11)

| Track | Status | Gate |
|-------|--------|------|
| **P0** contract completeness (E-01–E-43) | **Done** | `make validate-release-matrix` |
| **P1** depth (E-14–E-19) | **Done** | `make validate-p1` |
| **P1.5** LangGraph LG-1–LG-6 | **Done** | query unit + contract |
| **P1.6** INF-P1–P4, OBS-P1–P5 | **Done** | infra/obs contract tests |
| **P2** enterprise hardening (E-21–E-44, E-34, E-24, E-25) | **Done** | `make validate-p2` |
| **P3** advanced product (E-30–E-33) | **Done** | `make validate-p3` |
| **Post-P3** federation research, query quota suffix, mTLS listener | **Done** | `test_federated_research.py`, `test_mtls_config.py` |
| **rag-v1.0 CI gate** | **Done** | `make validate-rag-v1` |
| **Live cutover** | Operator | `make health`, `make migrate`, `RAGAS_GATE=1`, `LOAD_GATE=1` |

### 22.2 Open questions (resolved)

| ID | Resolution |
|----|------------|
| **OQ1** | `docs/MANAGED_STORES.md` + Helm `stores.mode` |
| **OQ2** | `docs/EMBED_DIMENSION_MIGRATION.md` + E-25 |
| **OQ3** | E-32 federated catalog + **federated research merge** (`federated_research.py`) |
| **OQ4** | `infra/docs/KEYCLOAK.md` §9 external IdP |
| **OQ5** | **Closed** — token-first MCP + optional JWT bridge |

### 22.3 Deferred beyond rag-v1.0

| Item | Notes |
|------|-------|
| Additional SaaS connectors | Out of scope for rag-v1.0; extend `get_connector()` when needed |
| Cross-region session stickiness | Catalog federation only |
| Qdrant sharding >5M chunks | INF-P6 scale-out docs |
| Redis LangGraph checkpointer | LG future |

### 22.8 TL-12 diagram remediation (docs debt)

Normative integration docs **MUST** convert remaining ASCII topology diagrams to Mermaid (FR-36):

| File | Section | Status |
|------|---------|--------|
| `query/docs/INTEGRATION.md` | §1 Network topology | **Done** v0.20 |
| `infra/docs/INTEGRATION.md` | §1 Network topology | **Done** v0.20 |
| `ingest/docs/INTEGRATION.md` | §1 Network topology | **Done** v0.20 |
| `observability/docs/INTEGRATION.md` | §1 Network topology | **Done** v0.20 |
| `observability/docs/STACK.md` | §2 Data flow | **Done** v0.20 |
| `inference/docs/INTEGRATION.md` | §1 Topology | **Done** v0.20 |
| `observability/docs/OTEL.md` | §1 Architecture | **Done** v0.20 |
| `docs/PERFORMANCE.md` | §1 hierarchy, §2.6 cache tree | **Done** v0.20 |

Directory trees (`├──`) in README files remain allowed per §21.2.

---

## 23. Coding standards

Full playbook: **[docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md)** · **G15** · **FR-38/39** · **TL-14/15/16**

Application code MUST be readable by a **novice developer**, safe at module boundaries, and consistent across sub-projects. Coding standards complement TDD (§19) and documentation (§21).

```mermaid
flowchart TB
    subgraph standards["Normative stack"]
        CS[CODING_STANDARDS.md]
        TDD[TESTING.md]
        DOC[DOCUMENTATION.md comments]
    end

    subgraph code["Application sub-projects"]
        Q[query/app/]
        I[ingest/app/]
        R[inference/reranker/]
    end

    CS --> Q & I & R
    TDD --> Q & I
    DOC --> Q & I & R
```

### 23.1 Scope

| Sub-project | Languages | Standard applies |
|-------------|-----------|------------------|
| `hybrid-rag-query` | Python 3.12+ | **Full** — LangGraph, FastAPI, httpx clients |
| `hybrid-rag-ingest` | Python 3.12+ | **Full** — FastAPI, Celery, parsers |
| `hybrid-rag-inference` | Python (reranker sidecar only) | **Full** for `reranker/sidecar.py`; vLLM is upstream image |
| `mod-chat` (planned) | TypeScript | §23.6 in playbook — ESLint, Prettier, strict TS |
| `hybrid-rag-infra` | Bash, Compose, YAML | Shell header convention (§23.7 in playbook) |
| `hybrid-rag-observability` | YAML, shell | Config comments; no application Python |

### 23.2 Core principles (summary)

| ID | Principle |
|----|-----------|
| **Boundary-first** | No `torch` / `vllm` in query or ingest (TL-02); no cross-sub-project Python imports (FR-20) |
| **Typed public APIs** | Type hints on all public functions; `RAGState` as `TypedDict` (TL-15) |
| **Novice docstrings** | Google-style module and function docs with spec § links (TL-13, FR-37) |
| **Structured logging** | `tenant_id`, `request_id`, `stage` in structured fields (TL-16) |
| **Fail closed** | Auth and ACL never leak document metadata (FR-03) |
| **Minimal diff** | Match existing patterns; no unrelated refactors in feature PRs |

### 23.3 Python layout and naming

Normative layout for application code:

```text
{sub-project}/app/
├── clients/           # thin store/inference HTTP wrappers
├── rag_graph.py       # LangGraph nodes (query)
├── rag_state.py       # RAGState TypedDict (query)
├── mcp_server.py      # FastAPI entry (query)
├── orchestrator.py    # FastAPI entry (ingest)
├── tasks.py           # Celery tasks (ingest)
└── telemetry.py       # OTel bootstrap
```

| Element | Convention |
|---------|------------|
| Modules / functions | `snake_case` |
| Classes | `PascalCase` |
| LangGraph nodes | `node_<stage>` |
| JSON / contract fields | `snake_case` per `SHARED_CONTRACTS.md` |
| Constants / env | `UPPER_SNAKE` |

### 23.4 LangGraph and FastAPI patterns

| Pattern | Requirement |
|---------|-------------|
| Node return | Partial `dict` merged into state — no in-place mutation |
| Timing | Every node records `timings_ms.<stage>` (FR-09) |
| Routing | `add_conditional_edges` + typed `_route_*` helpers |
| Routes | Pydantic validation; SSE events limited to FR-05 set |
| Health | Live dependency probes unless `STUB_HEALTH=true` (§1.5, FR-06) |
| Reference | `query/app/rag_graph.py`, `query/app/rag_state.py` |

### 23.5 HTTP clients and Celery (IF-4, ingest)

| Area | Rule |
|------|------|
| HTTP | `httpx` with pools and explicit timeouts (§18.16) |
| LLM retry | Max one retry on 5xx (§18.15) |
| Circuit breakers | Required before `rag-v1.0` (FR-28) |
| Celery | JSON-serializable args; idempotency key FR-01 |
| Embed | HTTP to inference — never load models in ingest worker |

### 23.6 Tooling (TL-14, FR-39, NFR-26)

| Tool | Purpose | Config location |
|------|---------|-----------------|
| **Black** | Formatting, line length **100** | `pyproject.toml` `[tool.black]` |
| **Ruff** | Lint (`E`, `F`, `I`, `UP`, `B` minimum) | `pyproject.toml` `[tool.ruff]` |
| **Root Makefile** | `make lint`, `make format`, `make bootstrap`, `make health` | Repo root `Makefile` |
| **mypy** / **pyright** | Optional static types on `app/` | CI when adopted |
| **pytest** | Tests per §19 | `tests/` per sub-project |

```bash
# Illustrative — root Makefile (preferred) or per sub-project
make lint          # ruff check + black --check
make format        # black application paths
make test          # pytest when tests/ exists
pytest tests/unit tests/contract -q --tb=short
```

Sub-projects **SHOULD** expose `make lint` running Ruff + Black when `pyproject.toml` is present. **Root** `Makefile` provides `make lint`, `make format`, `make bootstrap`, and `make health` across all planes.

### 23.7 Security and error handling (coding)

- Never log JWTs, API keys, or full document bodies at INFO.
- Catch specific exceptions — no bare `except:` .
- Map upstream failures to degrade ladder (§6.3.2) or structured HTTP errors (§7.7).
- `tenant_id` required on every retrieval code path (FR-02).

### 23.8 PR coding gate

Before merge, authors confirm [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) §8 checklist:

- [ ] Ruff + Black pass (when configured)
- [ ] Type hints on new public APIs
- [ ] Docstrings on new public APIs
- [ ] No FR-20 / TL-02 violations
- [ ] Tests for behavior changes (§19)
- [ ] Structured logs where applicable (TL-16)

### 23.9 Relation to documentation (§21)

| Topic | Primary section |
|-------|-----------------|
| Docstrings and comments | §21.4 + [DOCUMENTATION.md](./docs/DOCUMENTATION.md) §4 |
| Code layout, lint, patterns | **§23** + [CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) |
| Tests with code | §19 + [TESTING.md](./docs/TESTING.md) |

---

## 24. Document index

| § | Topic | Module |
|---|-------|--------|
| 1 | Executive summary + **implementation inventory** (§1.4–1.5) + stack (§1.3) | platform |
| 2 | Goals, FR/NFR | platform |
| 3 | **Modular architecture** (IF-1 … IF-6) | platform |
| 3A | Logical reference diagram | platform |
| 4 | Shared contracts + **DDL** (§4.4.1) + **JSON schemas** (§4.7) | mod-kernel |
| 5 | Ingestion | `ingest/` |
| 5A | Stack integration summaries | infra, inference, observability |
| 6–7 | Query + MCP + **sessions** (§7.11) | `query/` |
| 8 | Chat BFF (optional) | mod-chat |
| 9 | Security + OIDC (IF-6) | cross-cutting |
| 10 | Observability sub-project (**§10.5 SigNoz**) | `observability/` |
| 11–12 | Config + deployment + bootstrap | per-module / sub-project |
| 12.5–12.8 | Bootstrap, releases, Packer, **shipped artifacts** | platform |
| 13–14 | Evaluation + TDD (§13.4) + phases | cross-cutting |
| 15–16 | API examples + glossary | — |
| 17 | Architecture decisions | platform |
| 18 | Performance (§18.1–18.17) | per-module refs |
| 19 | **Test-driven development** | [docs/TESTING.md](./docs/TESTING.md) |
| 21 | **Documentation engineering** | [docs/DOCUMENTATION.md](./docs/DOCUMENTATION.md) |
| 23 | **Coding standards** | [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) |
| 22 | **What to spec next** (v0.25 implementation) | [docs/SPEC_ROADMAP.md](./docs/SPEC_ROADMAP.md) |
| 23 | **Coding standards** | [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) |
| — | [modules/schemas/](./modules/schemas/) | JSON Schema contracts §4.7 |
| — | [ingest/migrations/](./ingest/migrations/) | Catalog DDL §4.4.1 |
| — | [docs/USER_GUIDE.md](./docs/USER_GUIDE.md) | End-user chat and MCP |
| — | [docs/ADMIN_GUIDE.md](./docs/ADMIN_GUIDE.md) | Collections, ingest, ACL, quotas |
| — | [docs/DEPLOYMENT_GUIDE.md](./docs/DEPLOYMENT_GUIDE.md) | Bootstrap, profiles, health |
| — | [docs/ARCHITECT_GUIDE.md](./docs/ARCHITECT_GUIDE.md) | Interfaces, topologies, security |
| — | [docs/DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md) | Onboarding, TDD, extending pipeline |
| — | [CONTRIBUTING.md](./CONTRIBUTING.md) | PR checklist |
| — | [docs/CODING_STANDARDS.md](./docs/CODING_STANDARDS.md) | Python/TS style, lint, patterns, PR gate |
| — | [docs/TESTING.md](./docs/TESTING.md) | TDD playbook, test pyramid, fixtures |
| — | [query/docs/PERFORMANCE.md](./query/docs/PERFORMANCE.md) | query plane tuning |
| — | [ingest/docs/PERFORMANCE.md](./ingest/docs/PERFORMANCE.md) | ingest throughput |
| — | [query/benchmarks/README.md](./query/benchmarks/README.md) | Ragas, k6, Locust eval |
| — | [ingest/docs/DOCLING.md](./ingest/docs/DOCLING.md) | Docling parser tier |
| — | [docs/SPEC_ROADMAP.md](./docs/SPEC_ROADMAP.md) | enhancement plan |
| — | [docs/PERFORMANCE.md](./docs/PERFORMANCE.md) | platform optimization playbook |
| — | [observability/dashboards/langfuse-hybrid-rag.json](./observability/dashboards/langfuse-hybrid-rag.json) | Langfuse dashboard artifact |
| — | [observability/scripts/synthetic_trace.py](./observability/scripts/synthetic_trace.py) | Synthetic trace validation |
| — | [modules/IMPLEMENTATION.md](./modules/IMPLEMENTATION.md) | language map stub |
| modules/ | Shared contracts (`mod-kernel`) |
| query/ | **Query sub-project** (MCP, RAG pipeline) |
| ingest/ | **Ingestion sub-project** (orchestrator, Celery workers) |
| infra/ | **Infrastructure sub-project** (stores, Keycloak, Caddy) |
| inference/ | **Inference sub-project** (vLLM, rerankers, smoke LLM) |
| observability/ | **Observability sub-project** (Langfuse, OTel, Jaeger) |
| packer/ | **Docker image supply chain** |
| — | [KEYCLOAK.md](./modules/KEYCLOAK.md) | stub → `infra/docs/KEYCLOAK.md` |
| — | [CADDY.md](./modules/CADDY.md) | stub → `infra/docs/CADDY.md` |

---

*Normative for a greenfield **Enterprise Hybrid RAG** product. Independent of any existing repository.*
