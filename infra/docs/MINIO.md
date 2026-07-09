# MinIO (hybrid-rag-infra)

**Ports:** 9000 (S3 API), 9001 (web console)  
**Owner:** `hybrid-rag-infra`  
**Init:** `make init-db` (includes `scripts/init-minio.sh`) or `make init-minio`

MinIO is the **S3-compatible object store** for raw documents, extracted images/diagrams, thumbnails, and staging uploads. Query never proxies blob bytes through MCP — chunk payloads carry **presigned GET URLs** (`image_url`).

---

## 1. Buckets

| Bucket | Purpose |
|--------|---------|
| `hybrid-rag` (default) | Production objects — PDFs, DOCX originals, extracted images |
| `hybrid-rag-staging` | Multipart uploads, connector sync scratch, failed-parse quarantine |

Override names via `MINIO_BUCKET` / `MINIO_BUCKET_STAGING` in `infra/.env`.

---

## 2. Object key layout

Normative path (kernel contract §9):

```text
{bucket}/{tenant_id}/{collection_id}/{document_id}/{version_id}/{object_kind}/{uuid}.{ext}
```

| `object_kind` | Examples | Written by |
|---------------|----------|------------|
| `raw` | `report.pdf`, `spec.docx` | ingest (connector / filesystem) |
| `images` | `fig-3a8c.png`, `diagram.svg` | ingest (parser / VLM pipeline) |
| `thumbnails` | `fig-3a8c_thumb.jpg` | ingest (optional resize) |
| `exports` | `bundle.zip` | ingest (admin export jobs) |

**Chunk payload:** Qdrant `image_url` stores the **object key** (not a public URL). Query resolves presigned URLs at answer time using `MINIO_QUERY_*` credentials.

---

## 3. IAM (dev bootstrap)

`init-minio.sh` creates scoped users (replace with Vault/K8s secrets in prod):

| User | Policy | Capabilities |
|------|--------|--------------|
| `hybrid-rag-ingest` | `hybrid-rag-ingest-rw` | List, Get, Put, Delete on both buckets |
| `hybrid-rag-query` | `hybrid-rag-query-ro` | GetObject only (presign server-side) |

Dev defaults for passwords are in `infra/.env.example`. **Do not** use root credentials in application modules.

---

## 4. Application env

### hybrid-rag-ingest

```bash
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=hybrid-rag-ingest
MINIO_SECRET_KEY=change-me-ingest-minio
MINIO_BUCKET=hybrid-rag
MINIO_BUCKET_STAGING=hybrid-rag-staging
MINIO_REGION=us-east-1
```

### hybrid-rag-query (presigned URLs)

```bash
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=hybrid-rag-query
MINIO_SECRET_KEY=change-me-query-minio
MINIO_BUCKET=hybrid-rag
MINIO_PRESIGN_TTL_SECONDS=3600
```

---

## 5. Config (`config/infra.toml`)

```toml
[minio]
endpoint = "http://127.0.0.1:9000"
console = "http://127.0.0.1:9001"
bucket = "hybrid-rag"
bucket_staging = "hybrid-rag-staging"
region = "us-east-1"
presign_ttl_seconds = 3600

[minio.prefixes]
raw = "raw"
images = "images"
thumbnails = "thumbnails"
exports = "exports"
```

---

## 6. Console & health

```bash
# API liveness
curl -sf http://localhost:9000/minio/health/live

# Web UI (login: MINIO_ROOT_USER / MINIO_ROOT_PASSWORD)
open http://localhost:9001

# Verify bucket after init
docker run --rm --network hybrid-rag-net \
  -e MC_HOST_minio=http://minioadmin:change-me-in-production@minio:9000 \
  minio/mc ls minio/hybrid-rag
```

`make health` checks API liveness only. Run `make init-minio` after first `make up` to create buckets.

---

## 7. Performance notes

- **Presigned URLs** — query signs at answer time; no object bytes on MCP hot path
- **Multipart** — ingest uses multipart upload for files > 64 MB; stage in `hybrid-rag-staging` then copy to final key
- **Images** — store extracted figures as PNG/WebP; keep thumbnails ≤ 256px for UI previews
- **Prod** — local SSD or dedicated object tier; avoid NFS for hot paths

See [PERFORMANCE.md](./PERFORMANCE.md) §6.

---

## 8. Backup

`make backup` mirrors `hybrid-rag` and `hybrid-rag-staging` to `infra/backups/<stamp>/minio-*` via `mc mirror`.

For production DR, enable bucket replication or sync to external S3-compatible storage.
