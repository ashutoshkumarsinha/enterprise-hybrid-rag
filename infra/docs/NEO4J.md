# Neo4j (hybrid-rag-infra)

**Port:** 7687 (Bolt), 7474 (Browser)  
**Owner:** `hybrid-rag-infra`

## Role

Document hierarchy (`Document` → `Section` → `Chunk`), cross-references (`REFERENCES`), optional fulltext index for hybrid RRF with Qdrant.

Schema: parent [SHARED_CONTRACTS.md](../../modules/SHARED_CONTRACTS.md) §4.3.

## JVM (`config/infra.toml`)

| Profile | `heap_max` | `pagecache` |
|---------|------------|-------------|
| Dev | 2G | 512m |
| Prod single-node | 4G | 2G |
| Large corpus | 8G | 4G |

Set via compose `NEO4J_server_memory_*` env vars.

## Consumers

| Module | Access |
|--------|--------|
| hybrid-rag-ingest | MERGE nodes/edges, bulk UNWIND batches |
| hybrid-rag-query | read sessions, optional fulltext |

## Health

```bash
curl -sf http://localhost:7474
```

## Backup

`neo4j-admin database dump` — see `scripts/backup.sh` (extend for prod).
