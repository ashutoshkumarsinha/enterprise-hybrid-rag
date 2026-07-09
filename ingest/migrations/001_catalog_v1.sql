-- Catalog schema v1 — Enterprise Hybrid RAG
-- Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §4.4.1
-- Apply: ingest migrations runner or psql as ingest_rw after infra postgres-init.sh

BEGIN;

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    tier            TEXT NOT NULL DEFAULT 'standard'
                    CHECK (tier IN ('standard', 'professional', 'regulated')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_quotas (
    tenant_id               TEXT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    max_chunks              BIGINT NOT NULL DEFAULT 10000000,
    max_collections         INT NOT NULL DEFAULT 100,
    query_qps               NUMERIC(10,2) NOT NULL DEFAULT 2.0,
    max_concurrent_streams  INT NOT NULL DEFAULT 50,
    max_storage_bytes       BIGINT NOT NULL DEFAULT 536870912000,
    max_embed_tokens_day    BIGINT NOT NULL DEFAULT 10000000,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collections (
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    collection_id   TEXT NOT NULL,
    display_name    TEXT,
    description     TEXT,
    default_acl     JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, collection_id)
);

CREATE TABLE IF NOT EXISTS documents (
    tenant_id           TEXT NOT NULL,
    collection_id       TEXT NOT NULL,
    document_id         TEXT NOT NULL,
    title               TEXT NOT NULL,
    source_uri          TEXT,
    source_system       TEXT,
    latest_version_id   TEXT,
    tombstoned          BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, collection_id, document_id),
    FOREIGN KEY (tenant_id, collection_id)
        REFERENCES collections(tenant_id, collection_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_versions (
    tenant_id       TEXT NOT NULL,
    collection_id   TEXT NOT NULL,
    document_id     TEXT NOT NULL,
    version_id      TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    chunk_count     INT NOT NULL DEFAULT 0,
    ingest_job_id   UUID,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, collection_id, document_id, version_id),
    FOREIGN KEY (tenant_id, collection_id, document_id)
        REFERENCES documents(tenant_id, collection_id, document_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    collection_id   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    mode            TEXT NOT NULL DEFAULT 'incremental'
                    CHECK (mode IN ('full', 'incremental', 'version')),
    manifest_uri    TEXT,
    files_total     INT NOT NULL DEFAULT 0,
    files_done      INT NOT NULL DEFAULT 0,
    chunk_count     INT NOT NULL DEFAULT 0,
    error_count     INT NOT NULL DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingest_jobs_tenant_status
    ON ingest_jobs (tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS acl_grants (
    grant_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    principal       TEXT NOT NULL,
    collection_id   TEXT,
    document_id     TEXT,
    permission      TEXT NOT NULL DEFAULT 'read'
                    CHECK (permission IN ('read', 'write', 'admin')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT acl_scope_check CHECK (
        collection_id IS NOT NULL OR document_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_acl_grants_lookup
    ON acl_grants (tenant_id, principal, collection_id, document_id);

CREATE INDEX IF NOT EXISTS idx_documents_tenant_collection
    ON documents (tenant_id, collection_id) WHERE NOT tombstoned;

COMMIT;
