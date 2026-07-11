# Cross-Collection Queries (E-30)

**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md §6.2 `DocumentScope` · OD3  
**MCP:** `research_documents` · `POST /research/stream`

Search across **multiple logical collections** within one tenant in a single RAG request.

---

## 1. Scope model

| Input | Behavior |
|-------|----------|
| `collection_id` only | Search that corpus (existing v1 behavior) |
| `additional_collection_ids` only | Search listed corpora |
| Both | Union — primary + additional corpora |
| Neither | Tenant-wide search (no `collection_id` payload filter) |

**Limit:** max **8** additional collections per request (MCP schema).

---

## 2. MCP example

```json
{
  "query": "Compare refund policy vs billing FAQ",
  "tenant_id": "acme-corp",
  "collection_id": "payments-api",
  "additional_collection_ids": ["billing-faq", "support-macros"]
}
```

Qdrant filter uses `MatchAny` on `collection_id` when multiple corpora are in scope.

---

## 3. Implementation

| Component | Change |
|-----------|--------|
| `RAGState.additional_collection_ids` | Carries extra corpora through LangGraph |
| `query/app/clients/qdrant.py` | `MatchAny` filter for multi-collection |
| `query/app/query_cache.py` | Cache key includes sorted additional IDs |
| `modules/schemas/mcp_research_documents.input.v1.json` | Optional `additional_collection_ids` array |

**Supervisor:** When any collection scope is pinned (`collection_id` or `additional_collection_ids`), `explicit_scope` is true and supervisor may be skipped per settings.

---

## 4. Performance

- Single hybrid search with one `MatchAny` filter (default)
- `scope_strategy=multi_top_k` — parallel per-collection retrieve + score merge (`MULTI_SCOPE_PARALLELISM`, default 4)

---

## 5. Validation

```bash
make validate-p3
```

Contract: `ingest/tests/contract/test_p3_cross_collection.py`
