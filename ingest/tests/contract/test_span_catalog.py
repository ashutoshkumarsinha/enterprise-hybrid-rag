"""E-06 ingest OTel span catalog."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INGEST_ROOT = REPO_ROOT / "ingest"
CATALOG_PATH = REPO_ROOT / "docs" / "releases" / "span_catalog.json"

sys.path.insert(0, str(INGEST_ROOT))


def test_ingest_telemetry_exports_catalog() -> None:
    from app.telemetry import INGEST_SPAN_CATALOG

    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    expected = set(data["ingest_spans"])
    assert INGEST_SPAN_CATALOG == expected
