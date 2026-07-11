# Qdrant (hybrid-rag-infra)

**Port:** 6333 (REST), 6334 (gRPC)  
**Owner:** `hybrid-rag-infra`

## Collection

| Setting | Source |
|---------|--------|
| Name | `qdrant_collection` in `config/infra.toml` |
| Dense dimension | `embed_dimension` (must match inference embed model) |
| Sparse vector | `bm25-text` (BM25-style lexical) |
| Distance | Cosine |

## Init

```bash
make init-db
```

Creates collection with dense + sparse vectors if missing. Payload indexes are created by `hybrid-rag-ingest` on first upsert per SHARED_CONTRACTS.

### Collection tuning (INF-P1)

`make init-db` applies `on_disk_payload` and optional INT8 scalar quantization:

| Env | Default | Purpose |
|-----|---------|---------|
| `QDRANT_ON_DISK_PAYLOAD` | `true` | Keep payloads on disk at scale (>100k chunks) |
| `QDRANT_INT8_QUANTIZATION` | `false` (dev) | Enable INT8 scalar quant for >500k chunks (`prod_500k` profile) |

Existing collections are patched idempotently via `PATCH /collections/{name}`.

## HNSW tuning (`config/infra.toml`)

| Key | Default | Notes |
|-----|---------|-------|
| `hnsw_m` | 16 | Raise to 24–32 for > 1M chunks |
| `hnsw_ef_construct` | 100 | Index build quality |
| `search_ef` | 128 | Query recall vs latency — raise to 192–256 at scale |
| `on_disk_payload` | true | **Required** at > 100k chunks |

## Performance by corpus size

| Chunks | `search_ef` | `hnsw_m` | RAM estimate | Notes |
|--------|-------------|----------|--------------|-------|
| < 100k | 128 | 16 | 4–8 GB | Default compose |
| 100k–500k | 128–192 | 16 | 8–16 GB | `on_disk_payload=true` |
| 500k–2M | 192–256 | 24 | 16–32 GB | INT8 quantization |
| > 2M | 256+ | 32 | 32+ GB | Shard by tenant (future) |

**RAM formula:** `vectors_gb ≈ (chunk_count × embed_dimension × 4) / 1e9` + ~20–40% HNSW overhead.

## Payload indexes (query performance)

Create indexes on filter fields used in every query:

- `tenant_id`, `collection_id`, `document_id`, `version_id`, `type`, `acl_principal`

Without indexes, filtered hybrid search degrades linearly with corpus size.

## Query client guidance

- Prefer **gRPC** port **6334** over REST **6333** for retrieve/upsert (`PREFER_QDRANT_GRPC=true`)
- `QDRANT_URL` remains the REST base URL for health/init; clients derive host for gRPC
- Always include `tenant_id` + `collection_id` in filter — reduces search space

| Env | Default (dev stub) | Live stack |
|-----|-------------------|------------|
| `QDRANT_GRPC_PORT` | `6334` | `6334` (compose maps host port) |
| `PREFER_QDRANT_GRPC` | `false` | `true` |

`GET /healthz` on query reports `checks.qdrant_transport` (`stub` \| `grpc` \| `rest`).

## Consumers

| Module | Access |
|--------|--------|
| hybrid-rag-ingest | upsert, delete on reindex |
| hybrid-rag-query | search, scroll (read-only client) |

## Health

```bash
curl -sf http://localhost:6333/readyz
```

## Backup

`make backup` — Qdrant snapshot API. See parent spec §9.1.
