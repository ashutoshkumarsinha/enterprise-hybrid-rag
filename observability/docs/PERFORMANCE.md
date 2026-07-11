# Observability Performance — hybrid-rag-observability

**Parent:** [ENTERPRISE_HYBRID_RAG_SPEC.md](../../ENTERPRISE_HYBRID_RAG_SPEC.md) §10, IF-5  
**Platform guide:** [PERFORMANCE.md](../../docs/PERFORMANCE.md) §7

Telemetry MUST NOT materially impact query TTFT. Observability performance means **low SDK overhead**, **efficient collector pipelines**, and **sampling under load**.

---

## 1. Design principles

| Principle | Rule |
|-----------|------|
| **Off hot path** | Langfuse + OTLP export async; never block SSE token stream on export ACK |
| **SDK only in apps** | No collector/Langfuse server in query/ingest images |
| **No payload bloat** | No raw chunk text in spans; truncate `rag.query` ≤ 120 chars |
| **Batch export** | OTel `BatchSpanProcessor`; collector `batch` processor |
| **Sample at scale** | Tail/probabilistic sampling in collector for high QPS (prod) |

**Target overhead:** < 5ms p95 added to query path from OTel + Langfuse SDK combined (async flush).

---

## 2. Application SDK (query / ingest)

### OpenTelemetry (Python)

```python
# BatchSpanProcessor — default in app/telemetry.py
# Do NOT use SimpleSpanProcessor in production
```

| Setting | Dev | Prod |
|---------|-----|------|
| `OTEL_BSP_SCHEDULE_DELAY` | 5s | 2s |
| `OTEL_BSP_MAX_EXPORT_BATCH_SIZE` | 512 | 512 |
| `OTEL_BSP_EXPORT_TIMEOUT` | 30s | 10s |
| `OTEL_TRACES_SAMPLER` | `always_on` | `parentbased_traceidratio` (0.1–0.25) |

**Ingest workers:** Celery instrumentation — one span per task, not per chunk.

### Langfuse (query / mod-chat only)

- Flush generations **after** SSE `done` event — not per token
- Skip `generation` span on cache hit (`from_cache=true`)
- Batch metadata: `timings_ms` as JSON attribute, not 8 separate child spans unless debugging

---

## 3. OTel collector tuning

Config: [../collector/otel-collector-config.yaml](../collector/otel-collector-config.yaml)

### Current processors

| Processor | Purpose |
|-----------|---------|
| `memory_limiter` | 512 MiB cap — prevents OOM under burst |
| `batch` | 5s timeout, 512 batch — amortize Jaeger export |
| `resource` | `deployment.environment`, `service.namespace` |

### Recommended prod additions (planned)

```yaml
# observability/collector/otel-collector-config.prod.yaml (planned)
processors:
  probabilistic_sampler:
    sampling_percentage: 25
  attributes/redact:
    actions:
      - key: rag.query
        action: truncate
        truncated_length: 120
```

| Pipeline | Receivers | Exporters | Notes |
|----------|-----------|-----------|-------|
| traces | otlp | jaeger, debug | add sampler at > 500 spans/s |
| metrics | otlp | prometheus | scrape `:8889` — low cardinality only |
| logs | otlp | debug | optional; prefer stdout in apps v1 |

**Health:** `:13133` — collector MUST be healthy before apps depend on it (bootstrap §12.5).

---

## 4. Langfuse stack

| Component | Performance note |
|-----------|------------------|
| `langfuse` | 2.x; `TELEMETRY_ENABLED=false` in compose |
| `langfuse-postgres` | SSD; connection pool sized for UI + API ingest |
| SDK traffic | HTTP to `:3000` — async from query; not on retrieve critical path |

**Prod:** separate Langfuse project per environment; rate-limit public API if exposed.

**Cloud option:** Langfuse Cloud — removes self-hosted Postgres ops; same SDK contract.

---

## 5. Jaeger

| Setting | Dev | Prod |
|---------|-----|------|
| Storage | in-memory (all-in-one) | Badger volume (`PROFILE=jaeger-persist`) |
| UI | `:16686` | internal network only |
| Trace retention | 24h (in-memory) | 7d (`JAEGER_TRACE_RETENTION=168h`) |

**Cardinality rule:** limit high-cardinality attributes (`request_id` ok; `chunk_id` per span — avoid).

---

## 6. Prometheus (optional `PROFILE=metrics`)

- Scrape collector `:8889` — not every app directly
- **Metric naming:** `rag_stage_ms` histogram with `stage` label — max 10 stage values
- Avoid per-tenant metric labels in v1 (cardinality explosion)

---

## 7. SigNoz (optional `PROFILE=signoz`)

Use when APM dashboards and SLO alerting exceed Jaeger capabilities. Normative spec: platform **§10.5** and [SIGNOZ.md](./SIGNOZ.md).

| Rule | Detail |
|------|--------|
| Single SDK endpoint | Apps → primary collector `:4317` only |
| Fan-out | Collector `otlp/signoz` → `signoz-otel-collector` or managed endpoint |
| Config | `collector/otel-collector-config.signoz.yaml` |
| Metrics | `rag_ttft_ms`, `rag_stage_ms` via `OTEL_METRICS_EXPORTER=otlp` or `SIGNOZ_ENABLED=true` (FR-40) | **Done** in `query/app/otel_metrics.py` |
| Dashboards | `dashboards/signoz-*.json` stubs — import via SigNoz UI |
| Alerts | `alerts/signoz-rules.yaml` |
| Prometheus alerts | `alerts/prometheus-rules.yaml` (`PROFILE=metrics`) |

```bash
export SIGNOZ_OTLP_ENDPOINT=signoz-otel-collector:4317
make up PROFILE=signoz
```

Do **not** point application `OTEL_EXPORTER_OTLP_ENDPOINT` at SigNoz directly.

---

## 8. Overhead budget

| Signal | Acceptable query overhead | Measurement |
|--------|---------------------------|-------------|
| OTLP span create + enqueue | < 2ms p95 | Compare `rag_pipeline` with `OTEL_SDK_DISABLED=true` |
| Langfuse generation flush | < 3ms p95 async | After stream complete |
| Collector ingest | < 10ms | Collector self-metrics |
| Jaeger write | non-blocking | batch exporter queue depth |

**CI gate (OBS-P3):** `benchmark_rag.py --compare-otel` — total p95 regression must stay below 5% with OTel SDK enabled (in-memory exporter benchmark path).

---

## 9. Anti-patterns

| Anti-pattern | Impact | Fix |
|--------------|--------|-----|
| Span per retrieved chunk | 25+ spans/query | One `store/qdrant/retrieve` span with `recall_count` |
| Sync Langfuse flush before SSE token | TTFT +200ms | Flush after stream |
| `always_on` sampling at 1k QPS | Collector OOM | `probabilistic_sampler` 10–25% |
| Full query text in span attributes | Storage + PII | Truncate 120 chars |
| Debug exporter in prod | CPU + I/O | Remove `debug` exporter |
| Separate OTLP endpoint per app feature | Connection sprawl | Single collector `:4317` |

---

## 10. Config (`observability.toml` → `[performance]`)

```toml
[performance]
collector_memory_limit_mib = 512
batch_timeout_seconds = 5
batch_send_size = 512
trace_sampling_percentage = 100      # dev; 25 in prod
langfuse_async_flush = true
metrics_cardinality_limit = 50
synthetic_trace_on_health = false
```

---

## 11. Planned optimizations (roadmap)

| ID | Optimization | Status |
|----|--------------|--------|
| OBS-P1 | `probabilistic_sampler` processor + prod config profile | **done** |
| OBS-P2 | `attributes/redact` for query string truncation in collector | **done** (signoz + prod configs) |
| OBS-P3 | `benchmark_rag.py --compare-otel` CI gate | **done** |
| OBS-P4 | Jaeger persistent storage compose profile | **done** |
| OBS-P5 | Prometheus alert rules for `rag_ttft_ms` p95 | **done** |
| OBS-P6 | Tail sampling for error traces (100% errors, 10% success) | future |

| OBS-P6 | Tail sampling for error traces (100% errors, 10% success) | future |

**v1.0 gate:** OBS-P1–P3 MUST pass before `obs-v1.0` tag.

---

## 12. SLO dashboards and burn-rate alerts

Per platform §18.14 — `observability/dashboards/` (OBS-P5):

| Panel | SLI | Alert threshold |
|-------|-----|-----------------|
| Availability | `/healthz` 200 rate | 99.9% monthly; burn 2×/1h |
| TTFT | `rag_ttft_ms` p95 | > 2s for 30m |
| Retrieval | `rag_stage_ms.retrieve` p95 | > 500ms for 15m |
| Ingest throughput | `ingest_chunks_per_second` | < 50% baseline 10m |
| Error budget | composite | 6× burn in 6h → critical |

---

## 13. Validation

```bash
cd observability
make up && make health
make synthetic-trace
```

Compare query p95 with and without:

```bash
OTEL_SDK_DISABLED=true cd ../query && make health
# vs
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317 make up
```

Regression acceptable if total p95 increase < 5%.
