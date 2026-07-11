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

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `image_tag` | string | `dev` | OCI tag on every `hybrid-rag-*` image; use `rag-v1.0.0` or sub-project tag |
| `registry` | string | `""` | Registry prefix without trailing slash, e.g. `ghcr.io/acme` |
| `push` | bool | `false` | Run `docker-push` post-processor after build |
| `vllm_upstream` | string | `vllm/vllm-openai:v0.6.6` | Upstream vLLM image mirrored as `hybrid-rag-vllm-openai` (inference only) |

Copy [versions.pkrvars.hcl.example](./versions.pkrvars.hcl.example) for a commented glossary.

## Image catalog (E-04)

Machine-readable: [docs/releases/images.json](../docs/releases/images.json)

| Image | Sub-project | Type | Upstream / Dockerfile |
|-------|-------------|------|------------------------|
| `hybrid-rag-query` | query | build | `query/Dockerfile` |
| `hybrid-rag-ingest-orchestrator` | ingest | build | `ingest/Dockerfile` |
| `hybrid-rag-ingest-worker` | ingest | build | `ingest/Dockerfile.worker` |
| `hybrid-rag-reranker` | inference | build | `inference/reranker/Dockerfile` |
| `hybrid-rag-vllm-openai` | inference | mirror | `vllm/vllm-openai:v0.6.6` |
| `hybrid-rag-qdrant` | infra | mirror | `qdrant/qdrant:v1.12.5` |
| `hybrid-rag-neo4j` | infra | mirror | `neo4j:5.26-community` |
| `hybrid-rag-redis` | infra | mirror | `redis:7-alpine` |
| `hybrid-rag-minio` | infra | mirror | `minio/minio:RELEASE.2024-12-18T13-15-44Z` |
| `hybrid-rag-postgres` | infra | mirror | `postgres:16-alpine` |
| `hybrid-rag-caddy` | infra | mirror | `caddy:2.8-alpine` |
| `hybrid-rag-keycloak` | infra | mirror | `quay.io/keycloak/keycloak:26.0` |
| `hybrid-rag-langfuse-postgres` | observability | mirror | `postgres:16-alpine` |
| `hybrid-rag-langfuse` | observability | mirror | `langfuse/langfuse:2` |
| `hybrid-rag-otel-collector` | observability | mirror | `otel/opentelemetry-collector-contrib:0.96.0` |
| `hybrid-rag-signoz-otel-collector` | observability | mirror | `signoz/signoz-otel-collector:0.88.12` |

Release compatibility: [docs/RELEASE_MATRIX.md](../docs/RELEASE_MATRIX.md)

## CI

```bash
packer validate query/packer/
packer build -only=hybrid-rag-query -var 'image_tag=ci-${GITHUB_SHA}' query/packer/
```

## Notes

- **Custom builds** (query, ingest, reranker): Packer uses the `docker` builder with project `Dockerfile`s.
- **Mirror builds** (infra, observability, vLLM): Packer pulls pinned upstream images, applies OCI labels, and re-tags under `hybrid-rag-*` for air-gapped registries.
- Compose files can reference built images by setting `image: hybrid-rag-query:${IMAGE_TAG}` instead of `build:` — see each sub-project `packer/README.md`.
