# Performance — hybrid-rag-ingest

**Parent:** [SPEC.md](../SPEC.md) · Platform §5.4.1, §18.4, FR-29

Normative ingest throughput and backpressure for enterprise deployments.

---

## 1. Throughput targets

| Profile | Sustained chunks/s | Bottleneck |
|---------|-------------------|------------|
| `gpu_24gb` | ≥ 50 | Embed :8001 |
| `cpu_dev` | ≥ 5 | Embed CPU |
| CI mock (no inference) | ≥ 1000 chunks/min | Parser only |

Measure: `benchmark_ingest.py` — platform §13.

---

## 2. Worker sizing

```text
workers_needed ≈ target_chunks_per_sec / (embed_batch_size × batches_per_sec_per_worker)
```

| Knob | Default | Rule |
|------|---------|------|
| `celery_concurrency` | 4 | × `embed_parallelism` ≤ embed GPU throughput |
| `embed_parallelism` | 4 | Match vLLM embed `max-num-seqs` headroom |
| `parse_workers` | 2 | CPU-bound; separate from embed |
| `batch_size` | 32 | Chunks per Celery task |

**NFR-18:** When query TTFT p95 degrades > 20% during ingest, reduce `celery_concurrency` or pause enqueue (FR-29).

---

## 3. Automated backpressure (FR-29)

| Signal | Threshold | Action |
|--------|-----------|--------|
| `celery_queue_depth` | > 500 | Log warning |
| `celery_queue_depth` | > 1000 | Pause orchestrator enqueue (HTTP 503 on new jobs) |
| Query `rag_ttft_ms` p95 | > 2s during ingest | Halve `celery_concurrency` via beat hook |
| `max_embed_tokens_day` | quota 90% | Throttle to 25% concurrency |

**Config:**

```toml
[ingest]
ingest_backpressure_warn_depth = 100
ingest_backpressure_pause_depth = 1000
ingest_max_chunks_per_minute = 0   # 0 = unlimited; set during peak query hours
```

---

## 4. Batching

| Stage | Batch size | Config key |
|-------|------------|------------|
| Embed API | 32–64 texts | `batch_size` |
| Qdrant upsert | 100 points | `qdrant_upsert_batch` |
| Neo4j UNWIND | 50 nodes | `neo4j_unwind_batch` |
| Redis dedup MGET | 100 keys | `dedup_mget_batch` |

FR-15/26: never single-chunk embed when batch API available.

---

## 5. Off-peak scheduling

| Job type | Schedule | Rationale |
|----------|----------|-----------|
| Full reindex | `off_peak_cron` default `0 22 * * *` | Avoid embed contention |
| Connector sync | Business hours OK if incremental | Hash dedup skips unchanged |
| VLM caption (`defer_vlm`) | Off-peak queue | Vision GPU isolated |

---

## 6. MinIO uploads

| Object kind | Strategy |
|-------------|----------|
| `raw/` | Multipart > 64 MB; stage in `hybrid-rag-staging` |
| `images/` | PNG/WebP; parallel upload per page |
| `thumbnails/` | Async after main image |

Check `max_storage_bytes` quota before PUT (§9.3).

---

## 7. Dedup efficiency (NFR-12)

Target ≥ 30% skip on incremental re-ingest:

- Redis `dedup:{content_hash}` before embed
- File registry `file:{path_hash}` on connector sync

---

## 8. Quota enforcement (FR-30)

Before job enqueue:

1. `SELECT` catalog `tenant_quotas`
2. Reject if `chunk_count + job_estimate > max_chunks`
3. HTTP 403 with `quota_exceeded` kind

---

## 9. Benchmarks

```bash
python benchmarks/benchmark_ingest.py --mock --fail-chunks-per-min 1000
python benchmarks/benchmark_ingest.py --chunks 500 --fail-chunks-per-min 50
```

---

## 10. Anti-patterns

| Anti-pattern | Fix |
|--------------|-----|
| Peak full reindex + peak query | Off-peak cron |
| `wait=true` on bulk Qdrant upsert | `wait=false` for bulk |
| Per-chunk Neo4j MERGE | UNWIND batches |
| Unbounded queue during outage | FR-29 pause at 1000 depth |
