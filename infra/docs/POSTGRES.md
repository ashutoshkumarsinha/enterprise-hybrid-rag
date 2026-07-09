# Postgres Catalog (hybrid-rag-infra)

**Port:** 5432  
**Databases:** `catalog` (platform), `keycloak` (identity — separate role)  
**Owner:** `hybrid-rag-infra`

## Roles (provisioned at init)

| Role | DSN env | Module |
|------|---------|--------|
| `ingest_rw` | `CATALOG_DSN` | hybrid-rag-ingest |
| `query_ro` | `CATALOG_DSN_RO` | hybrid-rag-query (catalog read) |
| `query_token_rw` | `CATALOG_DSN_TOKEN` | hybrid-rag-query (mcp_access_tokens) |

Passwords from `infra/.env` (`INGEST_RW_PASSWORD`, `QUERY_RO_PASSWORD`, `KEYCLOAK_DB_PASSWORD`).

The `keycloak` database and `keycloak` role are provisioned at init for the Keycloak service — see [KEYCLOAK.md](./KEYCLOAK.md).

Table DDL is owned by **hybrid-rag-ingest migrations** — infra only creates roles and default privileges.

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
