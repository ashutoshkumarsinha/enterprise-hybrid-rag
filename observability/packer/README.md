# Packer — hybrid-rag-observability

Mirrors pinned observability images to `hybrid-rag-*` names.

| Output image | Upstream |
|--------------|----------|
| `hybrid-rag-langfuse-postgres` | `postgres:16-alpine` |
| `hybrid-rag-langfuse` | `langfuse/langfuse:2` |
| `hybrid-rag-otel-collector` | `otel/opentelemetry-collector-contrib:0.96.0` |
| `hybrid-rag-signoz-otel-collector` | `signoz/signoz-otel-collector:0.88.12` |

```bash
make packer-build IMAGE_TAG=obs-v1.0.0
```

See [../../packer/README.md](../../packer/README.md).
