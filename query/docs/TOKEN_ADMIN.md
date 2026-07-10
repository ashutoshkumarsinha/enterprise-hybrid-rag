# MCP token admin API (hybrid-rag-query)

**Parent:** [SPEC.md](../SPEC.md) · Platform [§7.13](../../ENTERPRISE_HYBRID_RAG_SPEC.md#713-role-based-access-control--token-based-mcp) · [RBAC.md](./RBAC.md)

Normative HTTP surface for minting, listing, and revoking `rag_mcp_*` access tokens. All routes require `Authorization: Bearer` with permission `mcp.admin.tokens` (or `mcp.*`).

**Base path:** `/admin/mcp/tokens`  
**Content-Type:** `application/json`  
**OpenAPI:** this document (implementation MAY export `query/openapi/token-admin.yaml`)

---

## POST /admin/mcp/tokens — mint

Creates a token row and returns the plaintext secret **once**.

**Request** — JSON Schema: [`mcp_access_token_mint.request.v1.json`](../../modules/schemas/mcp_access_token_mint.request.v1.json)

```json
{
  "tenant_id": "acme-corp",
  "principal": "user:alice",
  "label": "Alice Cursor",
  "role_template": "user",
  "permissions": null,
  "expires_in_days": 90
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `tenant_id` | yes | Must exist in `tenants` |
| `principal` | yes | `user:{sub}` or `service:{name}` |
| `label` | no | Human label for admin UI |
| `role_template` | no* | `viewer` \| `user` \| `collection-admin` \| `admin` — expands to `permissions[]` at mint |
| `permissions` | no* | Explicit permission list; overrides `role_template` when both set, `permissions` wins |
| `expires_in_days` | no | Default from `[auth].token_default_ttl_days` (90) |

**Response 201** — JSON Schema: [`mcp_access_token_mint.response.v1.json`](../../modules/schemas/mcp_access_token_mint.response.v1.json)

```json
{
  "token_id": "550e8400-e29b-41d4-a716-446655440000",
  "access_token": "rag_mcp_550e8400-e29b-41d4-a716-446655440000.x7K9mN2pQ8vR4sT1wY6zA3bC5dE0fG",
  "tenant_id": "acme-corp",
  "principal": "user:alice",
  "permissions": ["mcp.catalog.read", "mcp.graph.read", "mcp.session", "mcp.research"],
  "expires_at": "2026-10-07T00:00:00Z",
  "created_at": "2026-07-09T00:00:00Z"
}
```

**Errors:** `401 auth` · `403 forbidden` · `422 validation` · `404 tenant_not_found`

---

## GET /admin/mcp/tokens — list

Query parameters:

| Param | Default | Description |
|-------|---------|-------------|
| `tenant_id` | — | Filter by tenant (required unless caller has `mcp.*`) |
| `principal` | — | Optional filter |
| `include_revoked` | `false` | Include revoked rows |
| `limit` | `50` | Max 200 |
| `cursor` | — | Opaque pagination cursor |

**Response 200:**

```json
{
  "items": [
    {
      "token_id": "550e8400-e29b-41d4-a716-446655440000",
      "tenant_id": "acme-corp",
      "principal": "user:alice",
      "label": "Alice Cursor",
      "permissions": ["mcp.research"],
      "role_template": "user",
      "created_at": "2026-07-09T00:00:00Z",
      "expires_at": "2026-10-07T00:00:00Z",
      "revoked_at": null,
      "last_used_at": "2026-07-09T12:00:00Z"
    }
  ],
  "next_cursor": null
}
```

Never returns `secret_hash` or plaintext `access_token`.

---

## POST /admin/mcp/tokens/{token_id}/revoke — revoke

Idempotent. Sets `revoked_at = now()`.

**Response 200:**

```json
{
  "token_id": "550e8400-e29b-41d4-a716-446655440000",
  "revoked_at": "2026-07-09T18:00:00Z"
}
```

**Errors:** `404 token_not_found`

---

## Bootstrap CLI (dev)

When no admin token exists yet, operators MAY use a one-shot bootstrap (guarded by `ALLOW_TOKEN_BOOTSTRAP=true` in dev only):

```bash
cd query
python -m app.cli mint-mcp-token --tenant acme-corp --principal user:admin --template admin
```

Production: mint first token via break-glass DSN + `token_store.py` or Keycloak-authenticated admin with `jwt_bridge` + `mcp.admin.tokens`.

---

## Implementation modules

| Module | Responsibility |
|--------|----------------|
| `token_store.py` | `mint()`, `list_tokens()`, `revoke()`, `validate()` |
| `rbac.py` | `require_permission(ctx, "mcp.admin.tokens")` on all routes |
| `auth.py` | Parse Bearer on admin routes |

**DSN:** `CATALOG_DSN_TOKEN` — Postgres role `query_token_rw` (§4.4.3, `004_grant_query_roles_v1.sql`).
