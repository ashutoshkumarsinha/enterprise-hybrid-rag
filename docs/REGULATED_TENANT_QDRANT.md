# Regulated-Tier Per-Tenant Qdrant Collections (E-33)

**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md OD1 · SHARED_CONTRACTS §12  
**Migration:** `ingest/migrations/005_tenant_qdrant_suffix_v1.sql`

Regulated tenants MAY use a **dedicated physical Qdrant collection** instead of the shared global collection with payload `tenant_id` isolation.

---

## 1. Naming

| Tier | Physical collection |
|------|---------------------|
| `standard` / `professional` | `{QDRANT_COLLECTION}` e.g. `enterprise_hybrid_rag` |
| `regulated` (suffix set) | `{QDRANT_COLLECTION}_{suffix}` e.g. `enterprise_hybrid_rag_acme` |

Suffix rules: lowercase alphanumeric, `_` or `-`, max 63 chars.

---

## 2. Configuration

### Catalog (production)

Set via quota admin API after migration 005:

```bash
PUT /admin/tenants/acme-corp/quotas
{"qdrant_collection_suffix": "acme"}
```

Column: `tenant_quotas.qdrant_collection_suffix`.

### Dev / tests

```bash
QDRANT_TENANT_SUFFIX_JSON='{"acme-corp":"acme"}'
```

---

## 3. Code paths

| Module | Resolver |
|--------|----------|
| Ingest writes | `ingest/app/qdrant_collection.py` → `QdrantWriter.upsert_chunks` |
| Query search | `query/app/qdrant_collection.py` → `QdrantClient.hybrid_search` |
| Purge / delete | `delete_version`, `delete_tenant` use resolved physical name |

---

## 4. Provisioning

1. Apply migration 005: `cd ingest && make migrate`
2. Set suffix on regulated tenant quotas
3. Create collection: `QDRANT_COLLECTION=enterprise_hybrid_rag_acme EMBED_DIMENSION=768 make -C infra init-db`
4. Ingest tenant data into dedicated collection
5. Query resolves collection automatically from suffix map / catalog

---

## 5. Anti-patterns

| Anti-pattern | Why |
|--------------|-----|
| Suffix set but collection not created | Upsert/search 404 |
| Same suffix for two tenants | Data co-mingling |
| Mixed tier without suffix cleanup | Orphan points in global collection |

---

## 6. Validation

```bash
make validate-p3
```

Contract: `ingest/tests/contract/test_p3_regulated_qdrant.py`
