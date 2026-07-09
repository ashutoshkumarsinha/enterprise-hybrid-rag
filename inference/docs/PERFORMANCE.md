# Performance — hybrid-rag-inference

**Parent:** [SPEC.md](../SPEC.md) · Platform §6.11, §18.3, IF-4

Normative GPU inference tuning for enterprise RAG workloads.

---

## 1. Service isolation

| Service | Port | GPU | MUST NOT share GPU with |
|---------|------|-----|-------------------------|
| chat-llm | 8000 | yes | vision-llm (same card) |
| embedding | 8001 | yes/CPU | — (ingest + query share) |
| vision-llm | 8002 | yes | chat-llm |
| reranker | 8091 | CPU/GPU | — |
| reranker-fast | 8092 | CPU | — |

**NFR-18 rule:** Ingest embed and query embed share `:8001` — throttle ingest before reducing chat quality.

---

## 2. vLLM tuning (chat :8000)

| Flag | `gpu_24gb` | `a100_80gb` | Notes |
|------|------------|-------------|-------|
| `--max-num-seqs` | 8 | 32 | Caps concurrent KV cache |
| `--max-model-len` | 16384 | 32768 | Match `num_ctx` in query |
| `--enable-prefix-caching` | true | true | Repeated system prompts |
| `--gpu-memory-utilization` | 0.90 | 0.92 | Leave headroom (NFR-17) |
| `--dtype` | auto | auto | AWQ/GPTQ when available |

**TTFT drivers:** batch size, prefix cache hit, model quant level.

---

## 3. Embed server (:8001)

| Setting | Value | Rationale |
|---------|-------|-----------|
| Dedicated process | always | Isolate from chat KV |
| Batch size | up to 64 | FR-15/26 ingest batches |
| `max-num-seqs` | 16 | Headroom for query + ingest |
| CPU fallback (`dev`) | `e5-small` | Laptop only — not prod SLO |

**SLO:** p95 single-text embed < 80ms on GPU; batch-32 < 400ms.

---

## 4. Reranker sidecars

| Model | Port | Pairs/s (CPU) | Use |
|-------|------|---------------|-----|
| ms-marco-MiniLM | 8092 | ~200 | Stage 1 narrow 25→12 |
| bge-reranker-large | 8091 | ~40 | Stage 2 final top-k |

**Memory:** ~1 GB per sidecar — shared across all query replicas (FR-25).

POST `/predict` body: `{"query": "...", "documents": ["...", ...]}`

---

## 5. Queue depth and timeouts

| Client timeout | chat | embed | rerank |
|----------------|------|-------|--------|
| Connect | 5s | 3s | 3s |
| Read | 120s | 30s | 15s |

**Metrics (export to Prometheus):**

- `vllm_queue_depth`
- `vllm_kv_cache_usage_percent`
- `embed_batch_size_histogram`

Query circuit breakers open when queue depth > soft limit (§18.15).

---

## 6. Hardware profiles

See [SPEC.md](../SPEC.md) §6. Apply:

```bash
make up PROFILE=gpu_24gb
make health
```

| Profile | Concurrent chat streams | Concurrent embed batches |
|---------|-------------------------|--------------------------|
| `gpu_24gb` | 8 | 4 ingest + 2 query |
| `a100_80gb` | 32 | 8 ingest + 4 query |

---

## 7. Warm pools

| Policy | Setting |
|--------|---------|
| Models loaded at start | `make up` health pass |
| No unload between requests | vLLM always-on (not Ollama `keep_alive` in prod) |
| Smoke LLM | CI only — not on query hot path |

Query `warmup_clients()` probes all URLs at startup.

---

## 8. OOM playbook

| Symptom | Action |
|---------|--------|
| KV OOM during soak | Lower `--max-num-seqs`; reduce query `max_concurrent_streams` |
| Embed OOM | Lower batch size; split ingest workers |
| Multi-model on 24GB | Drop vision to off-peak only |

---

## 9. Benchmarks

Inference health is prerequisite for:

```bash
cd ../query && python benchmarks/benchmark_rag.py --limit 10
cd ../ingest && python benchmarks/benchmark_ingest.py --chunks 100
```

---

## 10. Anti-patterns

| Anti-pattern | Fix |
|--------------|-----|
| Chat + vision on same 24GB card | Separate GPUs or defer VLM |
| `max-num-seqs` = 64 on 24GB 70B | OOM — use quant or smaller model |
| No embed dedicated port | Contention with chat KV |
| Reranker in-process per query worker | HTTP sidecar |
