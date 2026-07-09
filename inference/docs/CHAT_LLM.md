# Chat LLM (vLLM)

**Service:** `chat-llm` · **Port:** 8000 · **Consumer:** hybrid-rag-query only

## Role

- Query **supervisor** (optional query rewrite)
- Grounded **answer** generation (streaming via MCP HTTP)

## vLLM launch

```bash
python -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port 8000 \
  --model meta-llama/Llama-3.2-3B-Instruct \
  --served-model-name meta-llama/Llama-3.2-3B-Instruct \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 16
```

## Contract

| App config | Server flag |
|------------|-------------|
| `[models].llm` | `--served-model-name` |
| `[query].num_ctx` | ≤ `--max-model-len` |
| `[query].max_answer_tokens` | passed as `max_tokens` in API |

## API

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-3.2-3B-Instruct","messages":[{"role":"user","content":"ping"}],"max_tokens":8}'
```

## Profiles

| Profile | Model |
|---------|-------|
| `gpu_24gb` | Llama-3.2-3B or Qwen-32B AWQ |
| `a100_80gb` | Llama-3.3-70B |
