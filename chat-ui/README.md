# mod-chat (E-18)

Optional React SPA + Express BFF for Enterprise Hybrid RAG. Consumes **hybrid-rag-query** only — never Qdrant, Neo4j, or Redis directly (TL-03).

## Stack

| Layer | Tech | Port |
|-------|------|------|
| BFF | Express + TypeScript | 4000 |
| UI | React + Vite | 5173 |
| Identity | Keycloak OIDC (PKCE) via `infra/keycloak` |

## Quick start (dev stub auth)

```bash
cd chat-ui
cp .env.example server/.env
npm install
npm run dev --workspace server   # terminal 1
npm run dev --workspace web      # terminal 2
```

1. Open http://localhost:5173
2. Click **Sign in** → stub session (`AUTH_STUB=true`)
3. Chat proxies to `QUERY_BASE_URL/research/stream` with MCP session tools

## Production OIDC

Set in `server/.env`:

```bash
AUTH_STUB=false
OIDC_ISSUER=http://keycloak:8080/realms/hybrid-rag
OIDC_CLIENT_ID=mod-chat
SESSION_SECRET=...
QUERY_BASE_URL=http://query:8010
QUERY_ACCESS_TOKEN=   # optional when JWT_BRIDGE forwards user access token
```

Redirect URIs are pre-configured in `infra/keycloak/hybrid-rag-realm.json` for `localhost:4000` and `localhost:5173`.

## BFF API (spec §8.4)

| Endpoint | Query backend |
|----------|---------------|
| `GET /api/collections` | `list_indexed_documents` (deduped collections) |
| `GET /api/collections/:id/documents` | `list_indexed_documents` |
| `POST /api/threads` | `create_conversation_session` |
| `GET /api/threads/:id/messages` | `get_conversation_history` |
| `POST /api/threads/:id/messages` | `/research/stream` (SSE proxy) |

Thread IDs map 1:1 to MCP `session_id` when query sessions are enabled.

## Tests

```bash
npm test --workspace server
```

Contract checks live in `ingest/tests/contract/test_chat_ui_scaffold.py`.
