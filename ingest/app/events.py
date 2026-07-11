"""Publish ingest catalog events for query cache invalidation."""

from __future__ import annotations

import json
import os


def publish_acl_changed(*, tenant_id: str, grant_id: str | None = None) -> None:
    """Emit ``acl.changed`` on the Redis events stream (best-effort)."""
    _publish_event({"type": "acl.changed", "tenant_id": tenant_id, "grant_id": grant_id})


def publish_connector_sync(
    *,
    tenant_id: str,
    collection_id: str,
    job_id: str,
    ingested: int,
) -> None:
    _publish_event(
        {
            "type": "connector.sync",
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "job_id": job_id,
            "ingested": ingested,
        }
    )


def publish_ingest_completed(
    *,
    tenant_id: str,
    collection_id: str,
    job_id: str,
    chunk_count: int,
) -> None:
    _publish_event(
        {
            "type": "ingest.completed",
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "job_id": job_id,
            "chunk_count": chunk_count,
        }
    )


def publish_tenant_purged(*, tenant_id: str) -> None:
    """Emit ``tenant.purged`` for query cache invalidation (E-21)."""
    _publish_event({"type": "tenant.purged", "tenant_id": tenant_id})


def _publish_event(payload: dict) -> None:
    url = os.environ.get("REDIS_URL")
    if not url:
        return
    stream = os.environ.get("REDIS_EVENTS_STREAM", "rag:events")
    try:
        import redis

        client = redis.from_url(url)
        client.xadd(stream, {"payload": json.dumps(payload)})
    except Exception:
        return
