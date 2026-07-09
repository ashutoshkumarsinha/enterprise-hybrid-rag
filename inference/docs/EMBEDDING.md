# Embedding Model (vLLM)

**Service:** `embedding` · **Port:** 8001 · **Consumers:** hybrid-rag-query, hybrid-rag-ingest

## Role

- Single dense vector per query (hybrid search)
- Batch embed at ingest (`embed(input=[...])`)

## vLLM launch

```bash
python -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port 8001 \
  --model intfloat/e5-base-v2 \
  --served-model-name intfloat/e5-base-v2 \
  --task embed
```

## Contract

| Setting | Value |
|---------|-------|
| `embed_dimension` | 768 (e5-base-v2) |
| Qdrant collection dim | must match |
| Max input tokens | ≥ 512 per chunk |

## API

```bash
curl http://localhost:8001/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"intfloat/e5-base-v2","input":["hello world"]}'
```

## CPU profile (`dev`)

Smaller embed model or CPU-only vLLM for CI without GPU.
