# Redis (hybrid-rag-infra)

**Port:** 6379  
**Owner:** `hybrid-rag-infra`

## Logical databases

| DB | Consumer | Purpose |
|----|----------|---------|
| 0 | hybrid-rag-query | Query result cache (`qcache:`) |
| 1 | hybrid-rag-ingest | Celery broker |
| — | hybrid-rag-ingest | Dedup keys (`dedup:{hash}`) |
| — | hybrid-rag-ingest → hybrid-rag-query | Domain events (Streams, optional) |

Configure via `REDIS_URL` and `CELERY_BROKER_URL` in application configs.

## Persistence and memory

Compose runs:

```text
redis-server --appendonly yes \
  --maxmemory ${REDIS_MAXMEMORY:-256mb} \
  --maxmemory-policy ${REDIS_MAXMEMORY_POLICY:-allkeys-lru}
```

| Setting | Default | Purpose |
|---------|---------|---------|
| `REDIS_MAXMEMORY` | `256mb` (dev) | Cap process RAM — see `infra.toml` `[performance]` profiles |
| `REDIS_MAXMEMORY_POLICY` | `allkeys-lru` | Evict least-recently-used keys when full (query cache DB 0) |

**Prod:** use `1gb`–`2gb` per `prod_500k` / `prod_2m` profiles. Celery broker (DB 1) SHOULD run on a dedicated Redis with `noeviction` when ingest load is high — single-instance dev shares memory with cache.

## Consumers

| Module | Keys / channels |
|--------|-----------------|
| hybrid-rag-ingest | Celery tasks, dedup, `ingest.completed` events |
| hybrid-rag-query | `qcache:{tenant}:{hash}`, cache version bump |

## Health

```bash
redis-cli -p 6379 ping
```
