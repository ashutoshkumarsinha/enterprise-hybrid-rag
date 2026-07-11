# Connectors (hybrid-rag-ingest)

All connectors implement:

```python
class Connector(Protocol):
    def list_objects(self, since: datetime | None) -> Iterator[SourceObject]: ...
    def fetch_bytes(self, key: str) -> bytes: ...
    def metadata(self, key: str) -> dict[str, str]: ...  # etag, mtime, acl hints
```

## Roadmap

| Connector | Phase | Auth | Notes |
|-----------|-------|------|-------|
| Filesystem | v1 | OS perms | Dev + air-gapped; `paths.documents_source_dir` |
| S3 / MinIO | P2 | IAM keys | Prefix per collection |
| SharePoint | P2 | OAuth app | Delta sync via `since` |
| Confluence | P3 | API token | Page tree → documents |
| Google Drive | P3 | OAuth | Shared drives |

**E-31:** `sharepoint` and `confluence` connectors ship stub-first (`CONNECTOR_STUB=true`). Production uses OAuth / API token env vars — see `ingest/app/connectors/sharepoint.py` and `confluence.py`.

## Config (`config/ingest.toml`)

```toml
[connectors]
filesystem_enabled = true
s3_enabled = false
sharepoint_enabled = false
confluence_enabled = false
connector_sync_interval_minutes = 60
```

## Scheduled sync

Enable Celery beat profile:

```bash
make up PROFILE=beat
```

Configure targets via env (see `ingest/.env.example`):

| Variable | Purpose |
|----------|---------|
| `CONNECTOR_BEAT_ENABLED` | `true` to register beat schedule |
| `CONNECTOR_SYNC_INTERVAL_MINUTES` | Tick interval (default 60) |
| `CONNECTOR_BEAT_TARGETS` | JSON array of `{tenant_id, collection_id, connector, mode, prefix}` |

Beat task `ingest.scheduled_connector_sync` enqueues connector jobs; workers fetch → parse → index.

## Catalog fields (FR-12)

Every synced object records:

- `source_uri`
- `source_system`
- `content_hash` (incremental detection)
