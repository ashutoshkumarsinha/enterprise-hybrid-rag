# JSON schemas (`mod-kernel`)

Normative machine-readable contracts for contract tests and CI validation.

**Parent:** [ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md) §4.7  
**Human-readable field lists:** [SHARED_CONTRACTS.md](../SHARED_CONTRACTS.md)

| File | Purpose |
|------|---------|
| `chunk_payload.v1.json` | Qdrant chunk payload (`index_schema_version=1`) |
| `mcp_research_documents.input.v1.json` | MCP `research_documents` tool arguments (+ `session_id`) |
| `mcp_create_conversation_session.input.v1.json` | MCP `create_conversation_session` |
| `mcp_get_conversation_history.input.v1.json` | MCP `get_conversation_history` |
| `events.ingest_completed.v1.json` | Redis Stream `ingest.completed` event |

**Validation (illustrative):**

```bash
# After pip install jsonschema
python -c "
import json, jsonschema
from pathlib import Path
schema = json.loads(Path('chunk_payload.v1.json').read_text())
sample = {'uuid':'00000000-0000-4000-8000-000000000001','tenant_id':'t','collection_id':'c',
  'document_id':'d','version_id':'v1','title':'T','text':'body','type':'text',
  'ingested_at':'2026-07-09T00:00:00Z'}
jsonschema.validate(sample, schema)
print('ok')
"
```

Contract tests **MUST** load these files from this directory (FR-33, E-15).
