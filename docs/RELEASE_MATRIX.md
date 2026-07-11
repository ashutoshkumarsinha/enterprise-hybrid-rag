# Release matrix — cross-plane compatibility (E-03)

**Parent:** [ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md) §12.6  
**Machine-readable:** [releases/compatibility.json](./releases/compatibility.json)  
**Image catalog:** [releases/images.json](./releases/images.json) · [packer/README.md](../packer/README.md)

Each sub-project tags independently. Platform releases (`rag-v*`) declare compatible sub-project tags and `index_schema_version`.

---

## 1. Tag patterns

| Sub-project | Git tag pattern | Example |
|-------------|-----------------|---------|
| Platform | `rag-v{major}.{minor}.{patch}` | `rag-v1.0.0` |
| infra | `infra-v*` | `infra-v1.0.0` |
| inference | `inf-v*` | `inf-v1.0.0` |
| observability | `obs-v*` | `obs-v1.0.0` |
| ingest | `ingest-v*` | `ingest-v1.0.0` |
| query | `query-v*` (or platform `rag-v*`) | `query-v1.0.0` |

**Do not conflate** FastAPI `version=` strings (e.g. `0.13.0-tenant-purge`) with release tags — those are dev build labels only.

---

## 2. Compatibility matrix

| Platform | infra | inference | observability | ingest | query | `index_schema_version` | Notes |
|----------|-------|-----------|---------------|--------|-------|------------------------|-------|
| **rag-v1.0.0** (target) | infra-v1.0.0 | inf-v1.0.0 | obs-v1.0.0 | ingest-v1.0.0 | query-v1.0.0 | **1** | First release train |
| rag-v1.0.0 | infra-v1.1.0 | inf-v1.0.0 | obs-v1.0.0+ | ingest-v1.0.0 | query-v1.0.0 | **1** | infra Keycloak — no schema break |
| rag-v1.1.0 (planned) | infra-v1.0.0+ | inf-v1.0.0+ | obs-v1.1.0 | ingest-v1.1.0 | query-v1.1.0 | **2** | Full reindex required |

Source of truth for automation: `docs/releases/compatibility.json`.

---

## 3. Breaking change triggers

Coordinated release notes required when any of:

| Change | Affected planes |
|--------|-----------------|
| `index_schema_version` bump | infra `init-db`, ingest migrations, query config, full reindex |
| MCP SSE event shape | query, mod-chat BFF |
| MCP tool removed | query, client SDKs, mod-chat |

---

## 4. Config alignment (`index_schema_version`)

All planes MUST agree on `index_schema_version` for a given platform release:

| Plane | Config file |
|-------|-------------|
| infra | `infra/config/infra.toml.example` |
| ingest | `ingest/config/ingest.toml.example` |
| query | `query/config/query.toml.example` |

Validate locally:

```bash
make validate-release-matrix
```

---

## 5. Release gate checklist

Before tagging `rag-v1.x`:

1. `index_schema_version` matches across infra, ingest, query configs
2. `embed_dimension` matches inference embed model output
3. `make init-db` + `cd ingest && make migrate`
4. `make test` (unit + contract) green on all planes
5. `benchmark_rag.py --ragas` gates pass
6. `load_test.py` soak thresholds (NFR-23)
7. Sub-project tags recorded in release notes per matrix row

See also [SPEC_ROADMAP.md](./SPEC_ROADMAP.md) §4 interface checklist.

---

## 6. Upgrade order

1. **infra** stores (backup first)
2. **inference** (keep model URLs stable when possible)
3. Rolling restart **query** replicas
4. Drain and upgrade **ingest** workers

Detail: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) §7.

---

## 7. Packer image tags

Images share the `image_tag` variable across sub-projects. For a platform release:

```bash
make packer-build-all IMAGE_TAG=rag-v1.0.0 REGISTRY=ghcr.io/myorg PUSH=true
```

Image naming catalog: [packer/README.md](../packer/README.md) · [releases/images.json](./releases/images.json).
