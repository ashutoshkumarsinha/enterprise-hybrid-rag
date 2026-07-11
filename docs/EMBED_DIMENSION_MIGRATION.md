# Embedding Dimension Migration Playbook (E-25)

**Resolves:** OQ2 — embed model swap without undefined behavior  
**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md §4, inference/docs/EMBEDDING.md

Changing `embed_dimension` (e.g. 768 → 1024 when swapping e5-base-v2 for a larger model) **requires a new Qdrant collection** and **full re-embed of all chunks**. In-place vector resize is not supported.

---

## 1. When this applies

| Change | Reindex required? |
|--------|-------------------|
| Same model, same dimension | No |
| Same dimension, different model weights | Recommended (quality) |
| **Different dimension** | **Yes — mandatory** |

Shared values that **must** match before cutover:

- `embed_dimension` — infra `config/infra.toml`, `EMBED_DIMENSION` env (ingest, query, inference)
- `qdrant_collection` — or use a new collection name for blue/green
- `index_schema_version` — bump on kernel release if schemas change

---

## 2. Pre-flight validation

```bash
# Dry-run: check env files + infra.toml agree on dimension
make validate-embed-dimension
# or
python scripts/migrate_embed_dimension.py --dry-run
```

Exit code `0` = consistent; `1` = mismatch detected.

Optional live check against Qdrant:

```bash
python scripts/migrate_embed_dimension.py --check-qdrant --qdrant-url http://127.0.0.1:6333
```

---

## 3. Blue/green migration procedure

### Phase A — Prepare (no downtime)

1. **Bump kernel config** in a branch; set target dimension everywhere:
   - `infra/config/infra.toml` → `embed_dimension`
   - `ingest/.env`, `query/.env`, `inference/.env` → `EMBED_DIMENSION`
2. **Deploy new inference embed model** on `:8001`; verify output dim with probe embed.
3. **Create new Qdrant collection** (suffix or versioned name):

   ```bash
   QDRANT_COLLECTION=enterprise_hybrid_rag_v2 EMBED_DIMENSION=1024 make -C infra init-db
   ```

4. Record in release notes + `docs/releases/compatibility.json` if `index_schema_version` changes.

### Phase B — Backfill

5. **Pause new ingest jobs** (optional maintenance window) or accept dual-write complexity.
6. **Re-embed all tenants** via ingest replay:
   - Export document manifest per tenant from catalog
   - Run batch re-ingest targeting `enterprise_hybrid_rag_v2`
   - Monitor Celery queue depth and embed GPU throughput (§12.4)

7. **Validate counts**: catalog `chunk_count` ≈ Qdrant point count per tenant/collection.

### Phase C — Cutover

8. Flip query + ingest to `QDRANT_COLLECTION=enterprise_hybrid_rag_v2`.
9. Rolling restart query replicas (`warmup_clients()`).
10. Run contract + benchmark suite (`make validate-p2`, `query/benchmarks/load_test.py`).

### Phase D — Cleanup

11. After retention window, delete old collection:

    ```bash
    curl -X DELETE "$QDRANT_URL/collections/enterprise_hybrid_rag"
    ```

12. Remove dual-collection config; update `docs/RELEASE_MATRIX.md`.

---

## 4. Rollback

If quality regresses before old collection deletion:

1. Revert `QDRANT_COLLECTION` and `EMBED_DIMENSION` env to previous values.
2. Restart query/ingest — old collection still serves traffic.
3. Drop partial `*_v2` collection if backfill incomplete.

---

## 5. Automation

| Tool | Role |
|------|------|
| `scripts/migrate_embed_dimension.py` | Consistency checks + printed checklist |
| `make validate-embed-dimension` | CI gate (E-25 contract) |
| `infra/scripts/init-db.sh` | Create collection with correct `size` |

---

## 6. Capacity impact

New dimension `D₂` vs old `D₁`:

```
vectors_gb ≈ (chunk_count × D₂ × 4 bytes) / 1e9 × 1.3
```

Plan Qdrant RAM before backfill (§12.3). Throttle ingest embed first under GPU pressure (§12.4 anti-pattern).
