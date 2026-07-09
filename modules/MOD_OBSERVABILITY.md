# Observability — moved to sub-project

The observability stack is a **separate sub-project**, not a file under `modules/`.

| Document | Path |
|----------|------|
| Sub-project README | [../observability/README.md](../observability/README.md) |
| Specification | [../observability/SPEC.md](../observability/SPEC.md) |
| Langfuse | [../observability/docs/LANGFUSE.md](../observability/docs/LANGFUSE.md) |
| Stack overview | [../observability/docs/STACK.md](../observability/docs/STACK.md) |
| Performance / overhead | [../observability/docs/PERFORMANCE.md](../observability/docs/PERFORMANCE.md) |
| OpenTelemetry / Jaeger | [../observability/docs/OTEL.md](../observability/docs/OTEL.md) |
| SigNoz (optional) | [../observability/docs/SIGNOZ.md](../observability/docs/SIGNOZ.md) |
| RAG integration | [../observability/docs/INTEGRATION.md](../observability/docs/INTEGRATION.md) |

**Project ID:** `hybrid-rag-observability`  
**Deploy:** `cd observability && make up`  
**Consumers:** `hybrid-rag-query`, `hybrid-rag-ingest`, `mod-chat` — SDK/exporter only.
