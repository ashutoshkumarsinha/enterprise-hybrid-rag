-- E-33 regulated tier — optional per-tenant Qdrant physical collection suffix
-- Spec: SHARED_CONTRACTS §12 · ENTERPRISE_HYBRID_RAG_SPEC.md OD1

BEGIN;

ALTER TABLE tenant_quotas
    ADD COLUMN IF NOT EXISTS qdrant_collection_suffix TEXT;

COMMENT ON COLUMN tenant_quotas.qdrant_collection_suffix IS
    'When set, physical Qdrant collection = {QDRANT_COLLECTION}_{suffix} for regulated isolation';

COMMIT;
