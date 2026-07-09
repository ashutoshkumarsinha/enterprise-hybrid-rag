# Conversation sessions (hybrid-rag-query)

**Parent:** [SPEC.md](../SPEC.md) · Platform [§7.11](../../ENTERPRISE_HYBRID_RAG_SPEC.md#711-conversation-sessions-persistence--management) · Pipeline [§6.13.7](../../ENTERPRISE_HYBRID_RAG_SPEC.md#6137-conversation-history-multi-turn)

---

## 1. Purpose

MCP hosts and mod-chat need **multi-turn conversational history** without building a separate message store. The query plane persists sessions in Postgres and wires history into the RAG pipeline when `session_id` is set.

| Concern | Owner |
|---------|-------|
| Session CRUD | `hybrid-rag-query` MCP tools + HTTP `/sessions` |
| Message storage | `conversation_messages` catalog table |
| History → LLM | `run_rag_pipeline()` + §6.13.7 token budget |
| Observability | `langfuse_session_id` = `session_id` |

---

## 2. Architecture

```mermaid
flowchart LR
    Client[MCP client / BFF]
    MCP[mcp_server.py]
    Store[session_store.py]
    PG[(conversation_*)]
    Graph[rag_graph.py]

    Client -->|create / list / research| MCP
    MCP --> Store
    Store --> PG
    MCP -->|session_id + query| Graph
    Graph -->|answer| MCP
    MCP -->|append turns| Store
```

**Implementation (planned):**

| Module | Role |
|--------|------|
| `app/session_store.py` | CRUD + principal checks (FR-43) |
| `app/mcp_server.py` | Tool handlers + HTTP routes |
| `app/rag_state.py` | `session_id`, `conversation_history` fields |

---

## 3. MCP tools

See platform §7.11.2 for argument tables.

| Tool | Schema |
|------|--------|
| `create_conversation_session` | `mcp_create_conversation_session.input.v1.json` |
| `get_conversation_history` | `mcp_get_conversation_history.input.v1.json` |
| `list_conversation_sessions` | Prose in §7.11.2 (schema TBD) |
| `update_conversation_session` | Prose in §7.11.2 (schema TBD) |
| `delete_conversation_session` | `{ session_id }` |
| `research_documents` | `mcp_research_documents.input.v1.json` (+ `session_id`) |

---

## 4. HTTP routes

| Route | Maps to |
|-------|---------|
| `POST /sessions` | `create_conversation_session` |
| `GET /sessions` | `list_conversation_sessions` |
| `GET /sessions/{id}` | Session metadata |
| `GET /sessions/{id}/messages` | `get_conversation_history` |
| `PATCH /sessions/{id}` | `update_conversation_session` |
| `DELETE /sessions/{id}` | `delete_conversation_session` |

Auth: same JWT rules as [MCP.md](./MCP.md) §Auth.

---

## 5. Multi-turn RAG flow

1. Client sends `research_documents({ session_id, query })`
2. Handler resolves principal from JWT → `user:{sub}`
3. `session_store.load_history(session_id, limit=max_history_turns)`
4. Build `RAGState` with `conversation_history: list[{role, content}]`
5. LangGraph runs retrieve → answer with history in LLM messages (§6.13.7)
6. On success: `session_store.append_turn(session_id, user_query, assistant_answer, rag_metadata)`
7. Return markdown per §7.8

**Streaming:** `POST /research/stream` buffers assistant text; persists on `done` event (or on error with partial flag).

---

## 6. Configuration

```toml
# query/config/query.toml
[sessions]
enabled = true
max_history_turns = 10
max_history_tokens = 2000
history_aware_supervisor = false
persist_assistant_sources = true
max_per_principal = 100
max_age_days = 90
```

**Env:**

```bash
CATALOG_DSN_SESSION=postgresql://query_session_rw:***@postgres:5432/catalog
```

Apply DDL: `psql $CATALOG_DSN -f ingest/migrations/002_conversation_sessions_v1.sql`

---

## 7. Security

| Check | Error |
|-------|-------|
| Session not found | 404 |
| Wrong `principal` | 404 |
| Wrong `tenant_id` | 404 |
| `sessions.enabled = false` | `session_id` ignored; warn log |

Never return 403 for foreign sessions — prevents enumeration.

---

## 8. mod-chat mapping

| mod-chat | MCP session |
|----------|-------------|
| `thread_id` | `session_id` (same UUID recommended) |
| `POST /api/threads` | `create_conversation_session` |
| Thread message list | `get_conversation_history` |

When sessions enabled, mod-chat **SHOULD NOT** duplicate full message bodies in local Postgres — query store is authoritative.

---

## 9. Testing

Contract tests (planned `query/tests/contract/`):

- `test_create_session_schema.py`
- `test_session_principal_isolation.py`
- `test_research_documents_appends_history.py`
- `test_history_token_truncation.py`

Golden fixtures: `query/tests/fixtures/session_turn_*.json`
