# Enterprise Hybrid RAG — Ingestion Sub-Project

**Project ID:** `hybrid-rag-ingest`  
**Independent deployable** from query, infra, inference, and observability.

Hosts the **ingestion plane** for the platform:

| Component | Default port | Role |
|-----------|--------------|------|
| **Orchestrator** | 8020 | Admin API, job enqueue, manifest load |
| **Celery workers** | — | Parse, embed, index writes |
| **Celery beat** | — | Scheduled connector sync (optional profile) |

Parent platform: [../ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md)

## Documents

| Document | Description |
|----------|-------------|
| [SPEC.md](./SPEC.md) | Sub-project boundary, ports, scaling |
| [docs/PIPELINE.md](./docs/PIPELINE.md) | Parse → chunk → embed → index stages |
| [docs/PERFORMANCE.md](./docs/PERFORMANCE.md) | Backpressure, batching, quotas |
| [docs/ADMIN_API.md](./docs/ADMIN_API.md) | `/admin/ingest/*` routes |
| [docs/CONNECTORS.md](./docs/CONNECTORS.md) | S3, filesystem, … |
| [docs/PARSERS.md](./docs/PARSERS.md) | PyMuPDF fast path + **Docling** quality tier |
| [docs/DOCLING.md](./docs/DOCLING.md) | Docling parser profile (TL-10) |
| [docs/INTEGRATION.md](./docs/INTEGRATION.md) | Stores, inference, events, observability |

## Quick start

```bash
cd ingest
cp .env.example .env
cp config/ingest.toml.example config/ingest.toml
# requires infra + inference stacks up first
make network
make up
make health
```

Scheduled connector sync:

```bash
make up PROFILE=beat
```

## Consumer contract (what this sub-project publishes)

- **Writes:** Qdrant points, Neo4j graph, MinIO objects, Postgres catalog (IF-1, IF-2)
- **Events:** `ingest.completed`, `ingest.failed` on Redis Stream (IF-3)
- **Does NOT expose:** MCP tools, `/research/stream`, chat LLM

## Repository layout

```text
enterprise-hybrid-rag/
├── query/              hybrid-rag-query (read-only on stores)
├── ingest/             ← this sub-project (ingest-v*)
├── infra/              hybrid-rag-infra
├── inference/          hybrid-rag-inference (embed + vision)
└── observability/      hybrid-rag-observability (OTLP)
```

**Versioning:** Tag `ingest-v1.x` independently of `rag-v1.x`.
