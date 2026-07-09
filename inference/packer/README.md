# Packer — hybrid-rag-inference

| Image | Type |
|-------|------|
| `hybrid-rag-reranker` | Built from `reranker/Dockerfile` |
| `hybrid-rag-vllm-openai` | Mirrored from `vllm/vllm-openai:v0.6.6` |

```bash
make packer-build IMAGE_TAG=inf-v1.0.0
```

Override upstream vLLM pin: `packer build -var 'vllm_upstream=vllm/vllm-openai:v0.6.6' packer/`

See [../../packer/README.md](../../packer/README.md).
