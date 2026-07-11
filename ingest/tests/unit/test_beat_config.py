"""Celery beat schedule configuration."""

from __future__ import annotations

import json
import os

import pytest

from app.beat_config import (
    beat_enabled,
    build_beat_schedule,
    load_beat_targets,
    sync_interval_minutes,
)


def test_beat_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONNECTOR_BEAT_ENABLED", raising=False)
    assert beat_enabled() is False
    assert build_beat_schedule() == {}


def test_beat_schedule_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNECTOR_BEAT_ENABLED", "true")
    monkeypatch.setenv("CONNECTOR_SYNC_INTERVAL_MINUTES", "30")
    schedule = build_beat_schedule()
    assert "ingest-scheduled-connector-sync" in schedule
    assert schedule["ingest-scheduled-connector-sync"]["task"] == "ingest.scheduled_connector_sync"
    assert schedule["ingest-scheduled-connector-sync"]["schedule"] == 1800


def test_load_beat_targets_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CONNECTOR_BEAT_TARGETS",
        json.dumps(
            [
                {
                    "tenant_id": "acme",
                    "collection_id": "payments-api",
                    "connector": "s3",
                    "mode": "incremental",
                }
            ]
        ),
    )
    targets = load_beat_targets()
    assert len(targets) == 1
    assert targets[0]["tenant_id"] == "acme"
    assert sync_interval_minutes() >= 1
