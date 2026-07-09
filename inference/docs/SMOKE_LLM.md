# Smoke / Test LLM

**Service:** `smoke-llm` · **Port:** 8011 · **Consumers:** CI, local dev without full GPU

## Purpose

Lightweight chat model for:

- `make smoke-test` in inference sub-project
- CI live gates when full `gpu_24gb` chat is too heavy
- Health verification without loading 32B weights

## Default model

`meta-llama/Llama-3.2-1B-Instruct` — fits CPU or small GPU.

## vLLM launch

```bash
python -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port 8011 \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --served-model-name meta-llama/Llama-3.2-1B-Instruct \
  --max-model-len 4096
```

## CI usage

Query repo `config/ci.toml`:

```toml
[models]
llm = "meta-llama/Llama-3.2-1B-Instruct"

[services]
vllm_url = "http://127.0.0.1:8011/v1"
```

**Not** for production quality evaluation — use `gpu_24gb` chat-llm for Ragas gates.

## Script

```bash
./scripts/smoke-test-llm.sh
```
