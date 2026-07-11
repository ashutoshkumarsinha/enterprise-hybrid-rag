"""Celery beat configuration for scheduled connector sync."""

from __future__ import annotations

import json
import os
from typing import Any


def beat_enabled() -> bool:
    return os.environ.get("CONNECTOR_BEAT_ENABLED", "").lower() in ("true", "1", "yes")


def sync_interval_minutes() -> int:
    return int(os.environ.get("CONNECTOR_SYNC_INTERVAL_MINUTES", "60"))


def load_beat_targets() -> list[dict[str, Any]]:
    """Parse ``CONNECTOR_BEAT_TARGETS`` JSON array of collection sync specs."""
    raw = os.environ.get("CONNECTOR_BEAT_TARGETS", "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("CONNECTOR_BEAT_TARGETS must be a JSON array")
    targets: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tenant_id = item.get("tenant_id")
        collection_id = item.get("collection_id")
        if not tenant_id or not collection_id:
            continue
        targets.append(
            {
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "version_id": item.get("version_id", "v1"),
                "mode": item.get("mode", "incremental"),
                "connector": item.get("connector", "s3"),
                "prefix": item.get("prefix"),
                "parser_profile": item.get("parser_profile"),
            }
        )
    return targets


def build_beat_schedule() -> dict[str, dict[str, Any]]:
    if not beat_enabled():
        return {}
    interval_s = max(sync_interval_minutes(), 1) * 60
    return {
        "ingest-scheduled-connector-sync": {
            "task": "ingest.scheduled_connector_sync",
            "schedule": interval_s,
        }
    }
