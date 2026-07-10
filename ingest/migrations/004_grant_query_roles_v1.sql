-- Post-DDL grants for query-plane Postgres roles
-- Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §4.4.2, §4.4.3, infra/docs/POSTGRES.md
-- Apply after 003_mcp_access_tokens_v1.sql

BEGIN;

-- Catalog read (all current and future tables in public)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO query_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO query_ro;

-- Conversation sessions (query_session_rw)
GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_sessions TO query_session_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_messages TO query_session_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO query_session_rw;

-- MCP access tokens (query_token_rw) — revoke via UPDATE, not DELETE
GRANT SELECT, INSERT, UPDATE ON mcp_access_tokens TO query_token_rw;

COMMIT;
