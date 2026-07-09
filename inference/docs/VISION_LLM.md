# Vision LLM (vLLM)

**Service:** `vision-llm` · **Port:** 8002 · **Consumer:** hybrid-rag-ingest only

## Role

Caption diagrams, flowcharts, and embedded images during ingest (`defer_vlm=true` in Celery worker).

## vLLM launch

```bash
python -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 --port 8002 \
  --model Qwen/Qwen2-VL-7B-Instruct \
  --served-model-name Qwen/Qwen2-VL-7B-Instruct \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85
```

## Contract

| App config | Server |
|------------|--------|
| `[models].vision` | `--served-model-name` |
| `vllm_vision_url` | `http://vision-llm:8002/v1` |

## Scheduling

Run vision server **off-peak** or on second GPU — conflicts with chat LLM on 24 GB cards.

## Disable

`PROFILE=dev` — vision service not started; ingest skips VLM or uses placeholder caption.
