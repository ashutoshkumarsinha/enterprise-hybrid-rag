# Reranker Sidecars (CrossEncoder)

**Not vLLM** — dedicated HTTP services to keep ~1 GB model weights out of each MCP worker.

| Service | Port | Model (default) |
|---------|------|-----------------|
| `reranker` | 8091 | `BAAI/bge-reranker-large` |
| `reranker-fast` | 8092 | `cross-encoder/ms-marco-MiniLM-L-6-v2` |

**Consumer:** hybrid-rag-query only

## API

### `POST /predict`

```json
{
  "query": "How do I rotate API keys?",
  "passages": ["chunk text 1", "chunk text 2"]
}
```

Response:

```json
{
  "scores": [0.87, 0.42]
}
```

### `GET /healthz`

```json
{"status": "ok", "model_loaded": true}
```

Returns `503` while model loads.

## hybrid-rag-query config

```toml
[models]
reranker = "BAAI/bge-reranker-large"
reranker_fast = "cross-encoder/ms-marco-MiniLM-L-6-v2"
reranker_url = "http://127.0.0.1:8091"
reranker_fast_url = "http://127.0.0.1:8092"
```

When URLs set, query image **must not** import `sentence-transformers` locally.

## Two-stage flow

1. Fast reranker: `final_recall_limit` → `rerank_stage1_top_n` (e.g. 25 → 12)
2. Full reranker: → `rerank_top_k` (e.g. 4)

## Implementation

See [../reranker/sidecar.py](../reranker/sidecar.py) — minimal FastAPI + CrossEncoder.

## Memory

Dual sidecars ≈ 2 GB RAM — size host accordingly.
