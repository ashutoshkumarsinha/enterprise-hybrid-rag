# Evaluation harness — hybrid-rag-query

**Parent:** Platform §13 · [PERFORMANCE.md](../docs/PERFORMANCE.md) §9 · **[TESTING.md](../../docs/TESTING.md)** (TDD)

Normative tools: **Ragas** (quality), **k6** (load primary), **Locust** (load alternative), **LangSmith** (graph traces), **pytest** (unit + contract, every PR).

---

## 1. Tool matrix

| Tool | TL | Purpose | CI tier |
|------|-----|---------|---------|
| **[Ragas](https://docs.ragas.io/)** | TL-08 | Faithfulness, relevancy, context recall | Nightly live |
| **[k6](https://k6.io/)** | TL-09 | Load, soak, SSE `/research/stream` | Pre-release |
| **[Locust](https://locust.io/)** | TL-09 | Same scenarios (Python-native) | Pre-release |
| `benchmark_rag.py` | — | Stage p50/p95, scope accuracy, `--ragas` | PR warn + nightly |
| `benchmark_ingest.py` | — | Ingest throughput (`ingest/benchmarks/`) | PR + nightly |
| `compare_benchmark_run.py` | — | Regression vs `baselines.json` | Nightly |
| `load_test.py` | — | Wrapper over k6 or Locust | Pre-release |
| LangSmith | TL-07 | LangGraph node regression (LG-4) | Eval CI optional |

---

## 2. Setup

```bash
cd query
pip install -r benchmarks/requirements.txt
cp benchmarks/baselines.json.example benchmarks/baselines.json
# k6: brew install k6  OR  https://k6.io/docs/get-started/installation/
# Locust: included in requirements.txt
```

---

## 3. Quality eval (Ragas)

```bash
export VLLM_URL=http://localhost:8000/v1   # judge + pipeline
python benchmarks/benchmark_rag.py \
  --golden-set benchmarks/golden_set.json \
  --limit 50 \
  --ragas \
  --fail-faithfulness 0.85 \
  --fail-answer-relevancy 0.80 \
  --fail-context-recall 0.75
```

Golden set format — platform §13.3:

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

Output: `benchmarks/last_ragas.json` — commit summaries in CI artifacts, not per-run in git.

---

## 4. Latency regression

```bash
python benchmarks/benchmark_rag.py --limit 20 --write-baseline
python benchmarks/compare_benchmark_run.py benchmarks/last_run.json benchmarks/baselines.json
```

---

## 5. Load / soak (k6 — primary)

```bash
export QUERY_URL=http://localhost:8010
k6 run benchmarks/k6/research_stream.js

# Soak (NFR-23)
k6 run --vus 50 --duration 2h benchmarks/k6/research_stream.js
```

Thresholds defined in `research_stream.js` — align with platform §13.1.

---

## 6. Load / soak (Locust — alternative)

```bash
locust -f benchmarks/locust/locustfile.py \
  --headless -u 50 -r 5 -t 30m \
  --host http://localhost:8010
```

---

## 7. Unified wrapper

```bash
python benchmarks/load_test.py --backend k6 --concurrency 50 --duration 30m
python benchmarks/load_test.py --backend locust --concurrency 50 --duration 30m
python benchmarks/load_test.py --backend k6 --concurrency 50 --duration 2h  # soak gate
```

---

## 8. CI tiers

| Tier | Commands |
|------|----------|
| **PR** | `ingest/benchmarks/benchmark_ingest.py --mock`; `benchmark_rag.py --limit 4` (warn) |
| **Nightly** | `benchmark_rag.py --ragas`; `compare_benchmark_run.py` |
| **Pre-release** | `load_test.py` 30m + 2h soak; chaos (staging) |

---

## 9. File layout

```text
query/benchmarks/
├── README.md                 # this file
├── requirements.txt          # ragas, locust, datasets
├── baselines.json.example
├── golden_set.json.example   # Ragas + scope accuracy
├── benchmark_rag.py          # golden-set latency + optional --ragas
├── benchmark_ingest.py       # lives in ingest/benchmarks/ (throughput)
├── compare_benchmark_run.py  # regression vs baselines.json
├── load_test.py              # k6 / Locust wrapper
├── k6/
│   └── research_stream.js
└── locust/
    └── locustfile.py
```
