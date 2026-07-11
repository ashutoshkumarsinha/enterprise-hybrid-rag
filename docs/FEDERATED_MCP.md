# Federated MCP — Multi-Region Catalog (E-32)

**Resolves:** OQ3 · extends E-24 multi-region read path  
**Spec:** ENTERPRISE_HYBRID_RAG_SPEC.md §17.1

Federated MCP provides a **unified catalog view** across regional `hybrid-rag-query` deployments while ingest and session writes remain on the primary region.

---

## 1. Architecture

```mermaid
flowchart TB
    CLIENT[MCP client / mod-chat]
    REG[Regional query — eu-west-1]
    PEER[Peer query — us-east-1]
    CAT_RO[(Postgres catalog replica)]
    CAT_PRI[(Postgres catalog primary)]

    CLIENT --> REG
    REG --> CAT_RO
    REG -.->|list_indexed_documents fan-out| PEER
    PEER --> CAT_PRI
```

| Concern | Primary region | Read region |
|---------|----------------|-------------|
| Ingest / writes | Yes | No |
| `CATALOG_DSN_SESSION` | Primary | Primary (until full federation) |
| `CATALOG_DSN_RO` | Optional replica | Regional replica |
| Catalog tool reads | Local + peer merge | Local + peer merge |

---

## 2. Configuration

```bash
FEDERATED_MCP_ENABLED=true
MCP_REGION=eu-west-1
MCP_PEER_ENDPOINTS_JSON='{"us-east-1":"https://query.us-east-1.example.com:8010"}'
FEDERATED_MCP_STUB=true   # dev — skip HTTP peer calls
```

Helm overlay (`deploy/helm/hybrid-rag/values-prod.yaml`):

```yaml
federatedMcp:
  enabled: true
  region: eu-west-1
  peerEndpoints:
    us-east-1: https://query.us-east-1.example.com:8010
```

ConfigMap emits `FEDERATED_MCP_ENABLED`, `MCP_REGION`, `MCP_PEER_ENDPOINTS_JSON`.

---

## 3. Runtime behavior

`query/app/federated_catalog.py` wraps the local `CatalogStore`:

- `list_indexed_documents` — merges local results with peer responses (dedupe by `document_id`)
- `get_document_metadata` — local first, then peer fallback
- Peer calls: `POST {peer}/mcp/tools/list_indexed_documents` and `get_document_metadata`

**Research / RAG** uses regional Qdrant replica (E-24). Federation applies to **catalog MCP tools** and **`research_documents`** when `FEDERATED_RESEARCH_ENABLED=true`.

### Research merge (`query/app/federated_research.py`)

1. Local region runs full LangGraph RAG against regional Qdrant.
2. Peer regions receive `POST /mcp/tools/research_documents` with `federated_internal: true` and `X-Federated-Service-Token`.
3. Responses merge:
   - **Sources** — union across regions (dedupe by `document_id` + `version_id`)
   - **Answer** — tenant **home region** wins when different from local; optional `FEDERATED_RESEARCH_APPEND=true` adds regional sections

```bash
FEDERATED_RESEARCH_ENABLED=true
FEDERATED_MCP_SERVICE_TOKEN=change-me-federation
MCP_TENANT_HOME_REGION_JSON='{"acme-corp":"us-east-1"}'
```

---

## 4. Rollout

1. Complete E-24 regional query + catalog replica deployment
2. Enable `FEDERATED_MCP_ENABLED` on read-region query pods
3. Register peer endpoints in `MCP_PEER_ENDPOINTS_JSON`
4. Verify `list_indexed_documents` returns union across regions
5. Monitor peer latency; set timeouts (5s default in code)

---

## 5. Future

- Sticky session federation across regions
- Cross-region vector index routing (beyond catalog + research merge)

See also: [`docs/MULTI_REGION.md`](./MULTI_REGION.md)

---

## 6. Validation

```bash
make validate-rag-v1
pytest ingest/tests/contract/test_federated_research.py
```
