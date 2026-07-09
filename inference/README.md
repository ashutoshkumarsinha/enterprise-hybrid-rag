# Enterprise Hybrid RAG — Inference Sub-Project

**Project ID:** `hybrid-rag-inference`  
**Independent deployable** from query, ingest, and store infrastructure.

Hosts all **model serving** for the platform:

| Role | Default port | Engine |
|------|--------------|--------|
| **Chat LLM** | 8000 | vLLM |
| **Embedding** | 8001 | vLLM (`--task embed`) |
| **Vision LLM** | 8002 | vLLM multimodal |
| **Reranker (full)** | 8091 | CrossEncoder HTTP sidecar |
| **Reranker (fast)** | 8092 | CrossEncoder HTTP sidecar |
| **Smoke / test LLM** | 8011 | vLLM tiny model (CI profile) |

Parent platform: [../ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md)

## Documents

| Document | Description |
|----------|-------------|
| [SPEC.md](./SPEC.md) | Sub-project boundary, ports, profiles |
| [docs/CHAT_LLM.md](./docs/CHAT_LLM.md) | Chat / supervisor / answer generation |
| [docs/EMBEDDING.md](./docs/EMBEDDING.md) | Dense vectors for Qdrant |
| [docs/VISION_LLM.md](./docs/VISION_LLM.md) | Diagram captioning at ingest |
| [docs/RERANKER.md](./docs/RERANKER.md) | Cross-encoder sidecars |
| [docs/SMOKE_LLM.md](./docs/SMOKE_LLM.md) | Lightweight LLM for CI / health |
| [docs/INTEGRATION.md](./docs/INTEGRATION.md) | How query & ingest connect |
| [docs/PERFORMANCE.md](./docs/PERFORMANCE.md) | vLLM tuning, GPU isolation, queue depth |

## Quick start

```bash
cd inference
cp .env.example .env
cp config/inference.toml.example config/inference.toml
# GPU profile: dev (smoke) | gpu_24gb | a100_80gb
make up PROFILE=gpu_24gb
make health
```

## Consumer URLs (application env)

```bash
# hybrid-rag-query
VLLM_URL=http://inference:8000/v1
VLLM_EMBED_URL=http://inference:8001/v1
RERANKER_URL=http://inference:8091
RERANKER_FAST_URL=http://inference:8092

# hybrid-rag-ingest
VLLM_EMBED_URL=http://inference:8001/v1
VLLM_VISION_URL=http://inference:8002/v1

# CI / smoke only
VLLM_SMOKE_URL=http://inference:8011/v1
```

Model names in app `config/*.toml` **must match** `--served-model-name` in this stack.

## Repository layout

```text
enterprise-hybrid-rag/
├── query/          # hybrid-rag-query — HTTP client → this stack
├── ingest/         # hybrid-rag-ingest — writes index via this stack
├── infra/          # hybrid-rag-infra — Qdrant, Neo4j, Redis, MinIO, Postgres, Caddy
├── observability/
└── inference/      # ← this sub-project (inf-v*)
```

**Versioning:** Tag `inf-v1.x` independently of `rag-v1.x`.
