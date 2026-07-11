# Enterprise Hybrid RAG — Observability Sub-Project

**Independent deployable** telemetry plane: **Langfuse**, **OTel collector**, **Jaeger**, and optional **SigNoz** / **Prometheus**. Application repos ship **SDKs/exporters only**.

Parent platform: [../ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md)

## Documents

| Document | Description |
|----------|-------------|
| [docs/STACK.md](./docs/STACK.md) | **Unified stack** — Langfuse + OTel + Jaeger in one compose |
| [docs/PERFORMANCE.md](./docs/PERFORMANCE.md) | SDK overhead, collector sampling, anti-patterns |
| [SPEC.md](./SPEC.md) | Sub-project specification (boundary, ports, CI) |
| [docs/OTEL.md](./docs/OTEL.md) | OpenTelemetry collector, SDK contract, Jaeger |
| [docs/LANGFUSE.md](./docs/LANGFUSE.md) | Langfuse deployment, trace hierarchy, SDK contract |
| [docs/INTEGRATION.md](./docs/INTEGRATION.md) | How query, ingest, and chat connect to this stack |
| [docs/SIGNOZ.md](./docs/SIGNOZ.md) | SigNoz / OTLP collector setup |

## Quick start

```bash
cd observability
cp .env.example .env
make up
make health
make synthetic-trace   # optional: emit test span → Jaeger
```

After `make up`, Langfuse keys are provisioned via headless init and synced with `make bootstrap-langfuse-keys` (see [docs/STACK.md](./docs/STACK.md#3-bootstrap)).

Optional profiles: `make up PROFILE=metrics` (Prometheus), `make up PROFILE=signoz` (Jaeger + SigNoz collector fan-out — see [docs/SIGNOZ.md](./docs/SIGNOZ.md) and platform §10.5).

| Service | URL |
|---------|-----|
| **Langfuse** (LLM traces) | http://localhost:3000 |
| Jaeger (OTel traces) | http://localhost:16686 |
| OTLP gRPC | localhost:4317 |
| OTLP HTTP | localhost:4318 |
| Collector health | http://localhost:13133 |
| Collector metrics | http://localhost:8889/metrics |

## Consumer configuration

Point RAG application modules at this stack (no code in this repo):

```bash
# hybrid-rag-query / mod-chat
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_HOST=http://langfuse:3000
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_EXPORTER_OTLP_INSECURE=true
export OTEL_SERVICE_NAME=hybrid-rag-query
export OTEL_TRACES_EXPORTER=otlp
export DEPLOY_ENV=dev

# hybrid-rag-ingest (OTLP only — no Langfuse generations)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_SERVICE_NAME=hybrid-rag-ingest
```

## Repository relationship

```text
enterprise-hybrid-rag/
├── query/              # hybrid-rag-query — SDK → this stack
├── ingest/             # hybrid-rag-ingest — OTLP → this stack
├── infra/              # hybrid-rag-infra (stores + Caddy)
├── inference/          # vLLM + rerankers + smoke LLM
└── observability/      # ← this sub-project (separate compose, CI, releases)
```

**Versioning:** Tag `obs-v1.x` independently of `rag-v1.x`.
