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

## Persistence

Compose runs `redis-server --appendonly yes` for dev durability.

## Consumers

| Module | Keys / channels |
|--------|-----------------|
| hybrid-rag-ingest | Celery tasks, dedup, `ingest.completed` events |
| hybrid-rag-query | `qcache:{tenant}:{hash}`, cache version bump |

## Health

```bash
redis-cli -p 6379 ping
```
