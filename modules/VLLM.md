# Inference — moved to sub-project

All model serving (vLLM chat, embed, vision, reranker sidecars, smoke test LLM) lives in **`hybrid-rag-inference`**.

| Document | Path |
|----------|------|
| Sub-project README | [../inference/README.md](../inference/README.md) |
| Specification | [../inference/SPEC.md](../inference/SPEC.md) |
| Chat LLM | [../inference/docs/CHAT_LLM.md](../inference/docs/CHAT_LLM.md) |
| Embedding | [../inference/docs/EMBEDDING.md](../inference/docs/EMBEDDING.md) |
| Vision LLM | [../inference/docs/VISION_LLM.md](../inference/docs/VISION_LLM.md) |
| Reranker | [../inference/docs/RERANKER.md](../inference/docs/RERANKER.md) |
| Smoke / test LLM | [../inference/docs/SMOKE_LLM.md](../inference/docs/SMOKE_LLM.md) |
| Integration | [../inference/docs/INTEGRATION.md](../inference/docs/INTEGRATION.md) |

```bash
cd inference && make up PROFILE=gpu_24gb && make health
```
