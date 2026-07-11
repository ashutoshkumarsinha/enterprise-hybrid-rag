-- Supplemental Postgres catalog indexes — INF-P2
-- Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §4.4.1, infra/docs/PERFORMANCE.md §5
-- Apply after ingest migrations (001–004):
--   psql "$CATALOG_DSN" -v ON_ERROR_STOP=1 -f infra/scripts/postgres-catalog-indexes.sql
-- Or: make -C infra init-catalog-indexes

BEGIN;

-- Query ACL load: tenant + principal IN (...)
CREATE INDEX IF NOT EXISTS idx_acl_grants_principal
    ON acl_grants (tenant_id, principal);

-- Admin grant listing ordered by created_at
CREATE INDEX IF NOT EXISTS idx_acl_grants_tenant_created
    ON acl_grants (tenant_id, created_at DESC);

-- Document catalog list + cursor pagination
CREATE INDEX IF NOT EXISTS idx_documents_tenant_collection_doc
    ON documents (tenant_id, collection_id, document_id)
    WHERE NOT tombstoned;

-- Tenant chunk quota aggregation (SUM chunk_count)
CREATE INDEX IF NOT EXISTS idx_document_versions_tenant
    ON document_versions (tenant_id);

-- Ingest job reconciliation / admin history
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_tenant_created
    ON ingest_jobs (tenant_id, created_at DESC);

-- Collection count per tenant (quota enforcement)
CREATE INDEX IF NOT EXISTS idx_collections_tenant
    ON collections (tenant_id);

COMMIT;
