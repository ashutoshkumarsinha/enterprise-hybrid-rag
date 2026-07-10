# Postgres Catalog (hybrid-rag-infra)

**Port:** 5432  
**Databases:** `catalog` (platform), `keycloak` (identity — separate role)  
**Owner:** `hybrid-rag-infra`

## Roles (provisioned at init)

| Role | DSN env | Module | Privileges |
|------|---------|--------|------------|
| `ingest_rw` | `CATALOG_DSN` | hybrid-rag-ingest | DDL + DML on catalog (migrations) |
| `query_ro` | `CATALOG_DSN_RO` | hybrid-rag-query | `SELECT` on catalog tables |
| `query_session_rw` | `CATALOG_DSN_SESSION` | hybrid-rag-query | R/W on `conversation_*` only |
| `query_token_rw` | `CATALOG_DSN_TOKEN` | hybrid-rag-query | R/W on `mcp_access_tokens` (revoke via `UPDATE`) |

Passwords from `infra/.env`:

- `INGEST_RW_PASSWORD`
- `QUERY_RO_PASSWORD`
- `QUERY_SESSION_RW_PASSWORD`
- `QUERY_TOKEN_RW_PASSWORD`
- `KEYCLOAK_DB_PASSWORD`

`infra/scripts/postgres-init.sh` creates all catalog roles at first Postgres boot.

The `keycloak` database and `keycloak` role are provisioned at init for the Keycloak service — see [KEYCLOAK.md](./KEYCLOAK.md).

Table DDL is owned by **hybrid-rag-ingest migrations** — see [ingest/docs/MIGRATIONS.md](../../ingest/docs/MIGRATIONS.md). After migrations `001`–`003`, apply **`004_grant_query_roles_v1.sql`** for table-scoped grants to `query_session_rw` and `query_token_rw`.

## Tables (logical)

- `tenants`, `collections`, `documents`, `document_versions`
- `ingest_jobs`, `acl_grants`
- `conversation_sessions`, `conversation_messages` (hybrid-rag-query — §4.4.2)
- `mcp_access_tokens` (MCP Bearer RBAC — §4.4.3)
- Optional: `chat_threads` (mod-chat legacy UI cache)

See parent spec IF-2 and [SHARED_CONTRACTS.md](../../modules/SHARED_CONTRACTS.md).

## Health

```bash
pg_isready -h 127.0.0.1 -p 5432
```

## Backup

`make backup` — `pg_dump` of `catalog` database.
