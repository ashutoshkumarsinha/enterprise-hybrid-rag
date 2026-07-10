# MCP server (hybrid-rag-query)

**Port:** 8010 · **Transports:** stdio + SSE

## Server identity

```
name: enterprise-hybrid-rag
version: 1.0.0
description: Hybrid RAG over ingested enterprise documents
```

## Required tools

| Tool | Purpose |
|------|---------|
| `research_documents` | Full RAG (blocking markdown); optional `session_id` for multi-turn |
| `create_conversation_session` | New persisted conversation (§7.11) |
| `list_conversation_sessions` | List sessions for current user |
| `get_conversation_history` | Load messages for a session |
| `update_conversation_session` | Title / scope pins |
| `delete_conversation_session` | Soft-delete session |
| `list_indexed_documents` | Catalog table via scroll / catalog RO |
| `visualize_document_graph` | Mermaid from Neo4j |
| `get_document_metadata` | JSON metadata + ACL |

**Session detail:** [SESSIONS.md](./SESSIONS.md)  
**RBAC:** [RBAC.md](./RBAC.md) — tool permissions §7.13  
**Token admin:** [TOKEN_ADMIN.md](./TOKEN_ADMIN.md) — mint/revoke `rag_mcp_*` tokens

## Optional admin tools

`list_collections`, `search_snippets`, `explain_scope` — require `mcp.admin.*` (see [RBAC.md](./RBAC.md)).

**Not in query:** `trigger_reindex` → use `ingest/` admin API.

## `research_documents` arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `query` | yes | User question |
| `tenant_id` | yes* | *From JWT if omitted |
| `collection_id` | no | Pin corpus |
| `document_id` | no | Pin document |
| `version_id` | no | Pin version |
| `langfuse_session_id` | no | Session grouping; SHOULD equal `session_id` when set |
| `session_id` | no | Persisted conversation UUID — load history + append turn |
| `create_session_if_missing` | no | Create session when omitted (default false) |
| `langfuse_trace_id` | no | 32-hex trace id |

## Markdown response contract

Stable order (BFF parsers depend on it):

```markdown
{answer with inline citations}

**Sources:**
1. [collection / doc §section p.N] — title (score 0.87)

---
*🔍 **MCP Search Telemetry:** ... timings ...*
```

## SSE endpoint

Public URL via Caddy: `https://{site}/mcp/sse` → upstream `:8010/sse`.

Direct dev: `http://127.0.0.1:8010/sse`

## stdio transport (Cursor / Claude Desktop)

```json
{
  "mcpServers": {
    "enterprise-hybrid-rag": {
      "command": "python",
      "args": ["-m", "app.mcp_stdio"],
      "cwd": "/path/to/enterprise-hybrid-rag/query",
      "env": {
        "MCP_ACCESS_TOKEN": "rag_mcp_<token_id>.<secret>",
        "QDRANT_STUB": "true",
        "EMBED_STUB": "true",
        "CHAT_STUB": "true"
      }
    }
  }
}
```

Or with OIDC JWT bridge (`JWT_STUB=true` dev only):

```bash
cd query
export MCP_ACCESS_TOKEN="$ACCESS_TOKEN"
python -m app.mcp_stdio
```

## Principles

1. MCP for discrete operations; HTTP for streaming, probes, and sessions
2. **Stateless handlers** — session state in Postgres when `[sessions].enabled` (§7.11)
3. Tenant from JWT or explicit `tenant_id`
