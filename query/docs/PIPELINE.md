# Query pipeline (hybrid-rag-query)

Parent: [SPEC.md](../SPEC.md) · Platform §6 · **[LangGraph](./LANGGRAPH.md)** · [PERFORMANCE.md](../../docs/PERFORMANCE.md)

## Orchestration

Pipeline stages run as a **LangGraph `StateGraph`** in `app/rag_graph.py`.  
LangSmith traces each run when `LANGCHAIN_TRACING_V2=true`.

## Stages (graph nodes)

| Stage | Description |
|-------|-------------|
| **supervisor** | Optional query rewrite (per-collection prompt) |
| **embed** | Single dense + sparse vector per request |
| **scope** | Resolve `DocumentScope` |
| **retrieve** | Hybrid Qdrant ± Neo4j fulltext RRF |
| **rerank** | Cross-encoder; optional two-stage |
| **graph** | Parent sections + cross-refs in context |
| **answer** | Grounded generation + citations |
| **cache_hit** | Optional Redis full-result cache |

**Invariant (FR-13):** one embed call per request — vector reused for scope + retrieve.

## Latency budget (GPU, scoped, warm)

| Stage | P95 budget | Skippable when |
|-------|------------|----------------|
| `cache_hit` | < 5ms | — |
| `scope` | < 20ms | Explicit pins |
| `supervisor` | < 400ms | `skip_supervisor_when_explicit` |
| `embed` | < 80ms | Never |
| `retrieve` | < 150ms | — |
| `rerank` | < 400ms | Two-stage (`rerank_stage1_top_n`) |
| `graph` | < 100ms | `graph_enrich_enabled = false` |
| `answer` (TTFT) | < 800ms P50 | Streamed via SSE |

**Total excl. LLM:** < 500ms (NFR-10, NFR-11).

## High-impact optimizations

| Priority | Technique | Config |
|----------|-----------|--------|
| 1 | Pin scope in UI/MCP | skips supervisor + scope inference |
| 2 | Two-stage rerank | `reranker_fast_url` + `rerank_stage1_top_n=12` |
| 3 | Dense scope mode | `scope_rerank_mode = dense` |
| 4 | HTTP reranker sidecar | `reranker_url` — shared GPU, light MCP workers |
| 5 | Client warmup | `warmup_on_startup`, `warmup_clients()` |
| 6 | Result cache | `query_cache_enabled` for FAQ workloads |
| 7 | Qdrant gRPC + filters | `tenant_id` + `collection_id` always in filter |

See [PERFORMANCE.md](../../docs/PERFORMANCE.md) for playbooks, anti-patterns, and profile presets.

## Benchmarks

```bash
cp benchmarks/baselines.json.example benchmarks/baselines.json
python benchmarks/benchmark_rag.py --limit 20 --write-baseline
```

Regression gates: platform spec §13, §18.7.

## Package layout

```text
query/app/
├── mcp_server.py
├── rag_graph.py          # LangGraph StateGraph
├── rag_state.py
├── langsmith_config.py
├── research_streaming.py
├── query_cache.py
└── client_factory.py
```

## Cache invalidation

Subscribe to Redis Stream `rag:events`; on `ingest.completed` with `cache_bump: true`, call `bump_cache_version(tenant_id, collection_id)`.
