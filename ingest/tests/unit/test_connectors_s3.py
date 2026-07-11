"""S3 connector stub mode."""

from __future__ import annotations

import os

from app.connectors.s3 import S3Connector


def test_stub_list_and_fetch() -> None:
    os.environ["CONNECTOR_STUB"] = "true"
    connector = S3Connector(tenant_id="acme", collection_id="payments-api")
    objects = list(connector.list_objects())
    assert len(objects) == 1
    payload = connector.fetch_bytes(objects[0].key)
    assert b"Stub connector document" in payload
    assert connector.is_stub is True
