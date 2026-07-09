-- Conversation session schema v1 — Enterprise Hybrid RAG
-- Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §4.4.2, §7.11
-- Apply after 001_catalog_v1.sql:
--   psql "$CATALOG_DSN" -f ingest/migrations/002_conversation_sessions_v1.sql
--
-- Role query_session_rw: GRANT INSERT/UPDATE/DELETE on conversation_* to query_session_rw

BEGIN;

CREATE TABLE IF NOT EXISTS conversation_sessions (
    session_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    principal       TEXT NOT NULL,
    title           TEXT,
    collection_id   TEXT,
    document_id     TEXT,
    version_id      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    message_count   INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_principal
    ON conversation_sessions (tenant_id, principal, updated_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_tenant_updated
    ON conversation_sessions (tenant_id, updated_at DESC)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES conversation_sessions(session_id) ON DELETE CASCADE,
    tenant_id       TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    rag_metadata    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT conversation_messages_content_len CHECK (char_length(content) <= 32000)
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_session
    ON conversation_messages (session_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_session_desc
    ON conversation_messages (session_id, created_at DESC);

-- Keep message_count in sync (application MAY also update in same txn as INSERT)
CREATE OR REPLACE FUNCTION conversation_messages_bump_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversation_sessions
    SET message_count = message_count + 1,
        updated_at = now()
    WHERE session_id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversation_messages_bump ON conversation_messages;
CREATE TRIGGER trg_conversation_messages_bump
    AFTER INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION conversation_messages_bump_count();

COMMIT;
