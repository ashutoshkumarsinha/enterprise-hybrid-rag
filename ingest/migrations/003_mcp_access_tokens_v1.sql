-- MCP access tokens — token-based RBAC
-- Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §4.4.3, §7.13
-- Apply after 002_conversation_sessions_v1.sql

BEGIN;

CREATE TABLE IF NOT EXISTS mcp_access_tokens (
    token_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    principal       TEXT NOT NULL,
    label           TEXT,
    permissions     JSONB NOT NULL DEFAULT '[]'::jsonb,
    role_template   TEXT,
    secret_hash     TEXT NOT NULL,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    CONSTRAINT mcp_access_tokens_permissions_array CHECK (jsonb_typeof(permissions) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_mcp_access_tokens_tenant
    ON mcp_access_tokens (tenant_id, revoked_at)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_mcp_access_tokens_principal
    ON mcp_access_tokens (tenant_id, principal)
    WHERE revoked_at IS NULL;

COMMIT;
