# Keycloak (hybrid-rag-infra)

**Port (host):** 8081 → container 8080  
**Realm:** `hybrid-rag`  
**Owner:** `hybrid-rag-infra`

Keycloak provides **OIDC identity** for `mod-chat` BFF and optional bearer validation on `hybrid-rag-query` MCP edge. Deployed in `infra/compose` — not in application images.

---

## 1. Services

| Component | Role |
|-----------|------|
| `keycloak` | OIDC issuer, admin console |
| `postgres` | `keycloak` database (separate from `catalog`) |

Realm import on first boot: [../keycloak/hybrid-rag-realm.json](../keycloak/hybrid-rag-realm.json)

---

## 2. URLs

| Context | URL |
|---------|-----|
| Admin console (host) | http://localhost:8081/admin |
| OIDC issuer (host) | http://localhost:8081/realms/hybrid-rag |
| OIDC issuer (Docker) | http://keycloak:8080/realms/hybrid-rag |
| JWKS | `{issuer}/protocol/openid-connect/certs` |

---

## 3. Pre-configured clients

| Client ID | Type | Consumer |
|-----------|------|----------|
| `mod-chat` | Public (PKCE) | Chat BFF + React SPA |
| `hybrid-rag-query` | Bearer-only | MCP JWT validation (optional prod) |

Redirect URIs (dev): `http://localhost:5173/*`, `http://localhost:4000/*`

---

## 4. Realm roles

Map to MCP permissions via `query.toml` `[rbac.role_permissions]` — platform §7.13.

| Role | MCP permissions (default) | Persona |
|------|---------------------------|---------|
| `viewer` | catalog.read, graph.read, session.read | Browse-only |
| `user` | + research, session write | Researcher |
| `collection-admin` | + admin.collections, admin.diagnostics | Team lead |
| `admin` | `mcp.*` (all tools) | Platform ops |

Map **tool access** to **MCP access tokens** (mint per user with `role_template`). Map **data access** to `acl_grants`:

- `user:{sub}` — individual
- `group:{team}` — team access via Keycloak group + catalog grant

Example: mint `user` token for Alice; grant `group:payments-team` read on `payments-api` collection.

---

## 5. Consumer env (`mod-chat`)

```bash
KEYCLOAK_URL=http://keycloak:8080
OIDC_ISSUER=http://keycloak:8080/realms/hybrid-rag
OIDC_CLIENT_ID=mod-chat
OIDC_CLIENT_SECRET=   # empty for public client + PKCE
SESSION_SECRET=generate-with-openssl-rand-hex-32
```

Langfuse user correlation: pass JWT `sub` as `langfuse_user_id`.

---

## 6. Bootstrap

```bash
cd infra
cp .env.example .env
make up          # starts postgres + keycloak (realm auto-import)
make health
```

1. Open http://localhost:8081/admin — login `admin` / `KEYCLOAK_ADMIN_PASSWORD` from `.env`
2. Create test users under realm **hybrid-rag** → Users
3. Assign realm roles `viewer`, `user`, `collection-admin`, or `admin`

For production, switch Keycloak command from `start-dev` to `start`, set `KC_HOSTNAME`, enable TLS, and use strong passwords.

---

## 7. Health

```bash
curl -sf http://127.0.0.1:8081/health/ready
```

Included in `make health`.

---

## 8. Security notes

- Do **not** expose Keycloak admin on the public internet without TLS and IP allowlists
- `hybrid-rag-query` bearer validation is defense-in-depth with Caddy `MCP_BEARER_TOKEN` — prefer OIDC JWT in multi-tenant prod
- Keycloak DB credentials live in `infra/.env` only
