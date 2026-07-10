# Enterprise Hybrid RAG — Query & MCP Sub-Project

**Project ID:** `hybrid-rag-query`  
**Independent deployable** from ingest, infra, inference, and observability.

Hosts the **query plane** and **MCP/HTTP gateway**:

| Surface | Default port | Role |
|---------|--------------|------|
| **MCP SSE + HTTP** | 8010 | `research_documents`, `/research/stream`, `/healthz` |
| **MCP stdio** | — | Claude Desktop / Cursor local transport |

Parent platform: [../ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md)

## Documents

| Document | Description |
|----------|-------------|
| [SPEC.md](./SPEC.md) | Sub-project boundary, ports, scaling |
| [docs/LANGGRAPH.md](./docs/LANGGRAPH.md) | LangGraph pipeline + LangSmith tracing |
| [docs/PIPELINE.md](./docs/PIPELINE.md) | Scope → retrieve → rerank → answer |
| [docs/PERFORMANCE.md](./docs/PERFORMANCE.md) | Rate limits, circuit breakers, HPA, pools |
| [benchmarks/README.md](./benchmarks/README.md) | **Ragas**, **k6**, **Locust** eval harness |
| [docs/MCP.md](./docs/MCP.md) | Tools, transports, markdown contract |
| [docs/HTTP.md](./docs/HTTP.md) | `/healthz`, error kinds |
| [docs/STREAMING.md](./docs/STREAMING.md) | SSE `/research/stream` events |
| [docs/INTEGRATION.md](./docs/INTEGRATION.md) | Stores, inference, observability, Caddy |

## Quick start

```bash
cd query
cp .env.example .env
cp config/query.toml.example config/query.toml
# requires infra + inference (+ optional observability) up first
make network
make up
make health
```

Public MCP via Caddy (infra edge):

```bash
cd ../infra && make up PROFILE=edge
# https://localhost:8080/mcp/sse → query:8010
```

### Live integration tests (nightly)

```bash
cp .env.live.example .env   # merge with local secrets/ports; disable all *_STUB flags
# Start infra + inference, then:
./scripts/run-integration.sh -q
# Strict mode (fail instead of skip when backends down):
LIVE_STACK_STRICT=1 ./scripts/run-integration.sh -q
# Optional: probe a running query container
export QUERY_BASE_URL=http://127.0.0.1:8010
```

Load probe (requires running query service):

```bash
python benchmarks/load_test.py --url http://127.0.0.1:8010 --requests 10 --concurrency 2
```

PR CI runs `pytest tests/unit tests/contract` only. See [../docs/TESTING.md](../docs/TESTING.md).

## Consumer contract

- **Reads:** Qdrant, Neo4j, Postgres catalog (RO), Redis cache, MinIO presigned URLs
- **Calls:** inference (embed, LLM, reranker) via HTTP
- **Exports:** Langfuse SDK + OTLP to observability sub-project
- **Does NOT:** write index, parse files, enqueue ingest jobs

## Repository layout

```text
enterprise-hybrid-rag/
├── query/              ← this sub-project (query-v*)
├── ingest/             hybrid-rag-ingest
├── infra/              hybrid-rag-infra (Caddy → query :8010)
├── inference/          hybrid-rag-inference
└── observability/      hybrid-rag-observability
```

**Versioning:** Tag `query-v1.x` independently of platform releases.
