# Performance — hybrid-rag-query

**Parent:** [SPEC.md](../SPEC.md) · Platform §6, §7.12, §18 · [LANGGRAPH.md](./LANGGRAPH.md)

Normative query-plane performance for enterprise deployments.

---

## 1. Latency budget (GPU, scoped, warm)

| LangGraph node | P95 budget | Skip when |
|----------------|------------|-----------|
| `check_cache` | < 5ms | — |
| `supervisor` | < 800ms | Explicit scope pins |
| `embed` | < 150ms | Cache hit |
| `scope` | < 20ms | Explicit pins |
| `retrieve` | < 200ms | — |
| `rerank` | < 400ms | Two-stage enabled |
| `graph_enrich` | < 150ms | L1 degrade |
| `answer` (TTFT) | < 2s total | Streaming |

---

## 2. LangGraph optimizations

| Technique | Config | Impact |
|-----------|--------|--------|
| Conditional edges | `skip_supervisor_when_explicit` | Skip supervisor node |
| Cache short-circuit | `query_cache_enabled` | `check_cache` → `answer` |
| Abstain early | `min_rerank_score` | `rerank` → `answer` skip graph+LLM |
| Degrade ladder | `[degradation]` | Platform §6.3.2 L1–L5 |

---

## 3. Connection pools (per replica)

Defaults per platform §18.16 — override in `query.toml`:

```toml
[performance]
connection_pool_qdrant = true
prefer_qdrant_grpc = true
qdrant_pool_max = 32
neo4j_pool_max = 16
redis_pool_max = 32
http_pool_max = 40
warmup_on_startup = true
```

`warmup_clients()` MUST run before accepting traffic (FR-14).

---

## 4. Adaptive `search_ef`

| Corpus size (scoped) | `search_ef` | Raise when |
|----------------------|-------------|------------|
| < 50k | 64 | recall gate fails |
| 50k–500k | 128 | default |
| 500k–2M | 192 | `retrieve` p95 > 200ms sustained |
| > 2M | 256 + INT8 | INF-P1 quantization |

**Adaptive rule (FR-31):** If `retrieve` p95 > budget × 1.2 for 5 min, increment `search_ef` by 32 (max 256). If p95 < budget × 0.8 for 30 min, decrement by 32 (min 64).

---

## 5. Rate limiting

Redis token bucket — keys per SHARED_CONTRACTS §6 `rlimit:`.

Check at MCP/HTTP middleware **before** `run_rag_pipeline()`.

```toml
[rate_limit]
enabled = true
tenant_queries_per_minute = 120
user_queries_per_minute = 30
max_concurrent_streams_per_user = 3
```

Platform defaults: §7.12. Tier overrides: catalog `tenant_quotas`.

---

## 6. Circuit breakers

Per platform §18.15 — implement in `client_factory.py` wrappers:

| Client | Open after | Fallback |
|--------|------------|----------|
| embed | 5 failures / 30s | L3 degrade |
| chat LLM | 5 failures / 30s | abstain message |
| Qdrant | 3 timeouts / 20s | L4 abstain |
| reranker | 5 failures / 30s | L2 dense top-k |

Emit `circuit_state` on OTel spans.

---

## 7. Caching

| Tier | Key | TTL |
|------|-----|-----|
| Full result | `qcache:{tenant}:{coll}:{sha256}` | 3600s |
| Embed vector | `embedcache:{sha256(text)}` | 86400s |
| ACL | in-process LRU | 60s |

Invalidate on `ingest.completed` with `cache_bump: true`.

---

## 8. HPA signals

| Metric | Scale up when | Scale down when |
|--------|---------------|-----------------|
| `rag_ttft_ms` p95 | > 1.5s for 5m | < 800ms for 15m |
| CPU utilization | > 60% for 5m | < 30% for 15m |
| `rate_limit_rejected_total` | sustained high | — (do not scale down on rejections) |

**Min replicas:** 2 in production. **Max:** bounded by inference `max-num-seqs`.

---

## 9. Benchmarks

```bash
pip install -r benchmarks/requirements.txt
python benchmarks/benchmark_rag.py --limit 20 --write-baseline
python benchmarks/benchmark_rag.py --limit 50 --ragas   # TL-08
k6 run -e QUERY_URL=http://localhost:8010 benchmarks/k6/research_stream.js   # TL-09
```

Detail: [benchmarks/README.md](../benchmarks/README.md).

---

## 10. Anti-patterns

| Anti-pattern | Fix |
|--------------|-----|
| New httpx client per request | Pooled clients (FR-25) |
| Rate limit after embed | Admission before graph |
| Ignore degradation metrics | Alert on L2+ > 5% |
| Scale replicas without inference headroom | Scale embed/chat GPU first |
