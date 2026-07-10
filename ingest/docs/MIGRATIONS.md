# Catalog migrations (hybrid-rag-ingest)

**Parent:** [SPEC.md](../SPEC.md) · Platform [§4.4](../../ENTERPRISE_HYBRID_RAG_SPEC.md#44-postgres-catalog-schema) · [§4.4.4](../../ENTERPRISE_HYBRID_RAG_SPEC.md#444-migration-runner)

Normative SQL migrations for the Postgres **catalog** database. Infra creates roles; ingest owns DDL and applies migrations.

---

## Files (ordered)

| # | File | Spec | Purpose |
|---|------|------|---------|
| 1 | `001_catalog_v1.sql` | §4.4.1 | Core catalog tables |
| 2 | `002_conversation_sessions_v1.sql` | §4.4.2 | MCP conversation sessions |
| 3 | `003_mcp_access_tokens_v1.sql` | §4.4.3 | MCP Bearer RBAC tokens |
| 4 | `004_grant_query_roles_v1.sql` | §4.4.3 | Table grants for `query_session_rw`, `query_token_rw` |

Apply in order. Each file is wrapped in `BEGIN`/`COMMIT` and uses `IF NOT EXISTS` where applicable.

---

## Prerequisites

1. `infra/scripts/postgres-init.sh` has run (roles: `ingest_rw`, `query_ro`, `query_session_rw`, `query_token_rw`).
2. `CATALOG_DSN` points at `ingest_rw` (migrations run as ingest).

---

## Manual apply (dev)

```bash
export CATALOG_DSN="postgresql://ingest_rw:${INGEST_RW_PASSWORD}@127.0.0.1:5432/catalog"

for f in ingest/migrations/00{1,2,3,4}_*.sql; do
  psql "$CATALOG_DSN" -v ON_ERROR_STOP=1 -f "$f"
done
```

---

## Migration runner (normative contract)

**Target:** `ingest/app/migrate.py` (planned) · Makefile target `make migrate`

| Requirement | Rule |
|-------------|------|
| **Ordering** | Lexicographic on filename prefix `NNN_` |
| **Tracking** | Table `schema_migrations(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ)` — created by runner on first use |
| **Idempotency** | Skip files whose `version` (basename without `.sql`) already exists in `schema_migrations` |
| **Lock** | `pg_advisory_lock(742001)` for duration of run — one migrator at a time |
| **DSN** | `CATALOG_DSN` env; fail fast if role is not `ingest_rw` |
| **Exit code** | `0` on success; non-zero on first SQL error (`ON_ERROR_STOP=1`) |

**CLI:**

```bash
cd ingest
make migrate                    # apply pending
python -m app.migrate --status  # list applied / pending
python -m app.migrate --dry-run # print pending files only
```

**Bootstrap integration:** root `make bootstrap` step 3 SHOULD invoke `cd ingest && make migrate` after infra health passes (platform §12.5).

---

## Post-migration grants

`004_grant_query_roles_v1.sql` runs **after** tables exist:

- `query_ro` — `SELECT` on all catalog tables
- `query_session_rw` — `SELECT`, `INSERT`, `UPDATE`, `DELETE` on `conversation_sessions`, `conversation_messages` only
- `query_token_rw` — `SELECT`, `INSERT`, `UPDATE` on `mcp_access_tokens` (no `DELETE` — revoke via `UPDATE`)

Re-run safe: uses `GRANT` idempotently.

---

## Rollback policy

Forward-only in v1. Destructive rollback requires manual `pg_dump` restore. Document breaking DDL in release notes and bump `index_schema_version` when vector payload changes.
