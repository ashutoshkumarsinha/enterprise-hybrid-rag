# Packer — Docker image builds

[Packer](https://developer.hashicorp.com/packer) builds and tags Docker images for each **hybrid-rag** sub-project.

| Sub-project | Packer config | Images produced |
|-------------|---------------|-----------------|
| [query](../query/packer/) | Dockerfile build | `hybrid-rag-query` |
| [ingest](../ingest/packer/) | Dockerfile builds | `hybrid-rag-ingest-orchestrator`, `hybrid-rag-ingest-worker` |
| [inference](../inference/packer/) | Dockerfile + mirror | `hybrid-rag-reranker`, `hybrid-rag-vllm-openai` (mirrored) |
| [infra](../infra/packer/) | Mirror upstream | `hybrid-rag-qdrant`, `hybrid-rag-neo4j`, … |
| [observability](../observability/packer/) | Mirror upstream | `hybrid-rag-langfuse`, `hybrid-rag-otel-collector`, … |

## Prerequisites

```bash
brew install packer   # or https://developer.hashicorp.com/packer/install
docker info           # Docker daemon running
packer plugins install github.com/hashicorp/docker
```

## Build all images

```bash
cp packer/versions.pkrvars.hcl.example packer/versions.pkrvars.hcl
# edit image_tag / registry

IMAGE_TAG=1.0.0 ./packer/build-all.sh
```

With private registry:

```bash
docker login ghcr.io
IMAGE_TAG=query-v1.0.0 REGISTRY=ghcr.io/myorg PUSH=true ./packer/build-all.sh
```

## Build one sub-project

```bash
cd query
packer init packer
packer build -var 'image_tag=dev' packer/
```

Or via Make:

```bash
cd query && make packer-build IMAGE_TAG=1.0.0
```

## Variables (all sub-projects)

| Variable | Default | Description |
|----------|---------|-------------|
| `image_tag` | `dev` | Image tag (and `latest` when tag ≠ `latest`) |
| `registry` | `""` | Optional registry prefix, e.g. `ghcr.io/acme` |
| `push` | `false` | Run `docker-push` post-processor after build |

## CI

```bash
packer validate query/packer/
packer build -only=hybrid-rag-query -var 'image_tag=ci-${GITHUB_SHA}' query/packer/
```

## Notes

- **Custom builds** (query, ingest, reranker): Packer uses the `docker` builder with project `Dockerfile`s.
- **Mirror builds** (infra, observability, vLLM): Packer pulls pinned upstream images, applies OCI labels, and re-tags under `hybrid-rag-*` for air-gapped registries.
- Compose files can reference built images by setting `image: hybrid-rag-query:${IMAGE_TAG}` instead of `build:` — see each sub-project `packer/README.md`.
