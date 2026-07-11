"""Connector sync — list objects, parse, and index."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.connectors import get_connector
from app.events import publish_connector_sync, publish_ingest_completed
from app.file_registry import get_file_registry, registry_key
from app.parsers.base import ParseContext
from app.pipeline import parse_document
from app.telemetry import get_tracer
from app.writers import write_chunks


def sync_collection(
    *,
    tenant_id: str,
    collection_id: str,
    version_id: str,
    connector: str = "s3",
    prefix: str | None = None,
    mode: str = "incremental",
    since: str | None = None,
    parser_profile: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Sync a collection from a connector into the parse + write pipeline."""
    tracer = get_tracer()
    job_id = job_id or str(uuid.uuid4())
    since_dt = datetime.fromisoformat(since) if since else None
    profile = parser_profile or os.environ.get("PARSER_PROFILE", "fast")
    registry = get_file_registry()
    connector_client = get_connector(
        connector,
        tenant_id=tenant_id,
        collection_id=collection_id,
        prefix=prefix,
    )

    ingested = 0
    skipped = 0
    chunk_total = 0
    errors: list[dict[str, str]] = []

    with tracer.start_as_current_span("connector.sync") as span:
        span.set_attribute("ingest.job_id", job_id)
        span.set_attribute("ingest.tenant_id", tenant_id)
        span.set_attribute("ingest.collection_id", collection_id)
        span.set_attribute("connector.type", connector)

        for obj in connector_client.list_objects(since_dt):
            key = registry_key(
                tenant_id=tenant_id,
                collection_id=collection_id,
                object_key=obj.key,
            )
            if mode == "incremental" and not registry.should_ingest(
                registry_key=key,
                etag=obj.etag,
            ):
                skipped += 1
                continue
            try:
                payload = connector_client.fetch_bytes(obj.key)
                suffix = Path(obj.key).suffix or ".txt"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(payload)
                    tmp_path = Path(tmp.name)
                try:
                    bucket = os.environ.get("MINIO_BUCKET", "hybrid-rag")
                    source_uri = f"s3://{bucket}/{obj.key}"
                    ctx = ParseContext(
                        tenant_id=tenant_id,
                        collection_id=collection_id,
                        document_id=obj.document_id,
                        version_id=version_id,
                        title=obj.document_id.replace("-", " ").title(),
                        source_uri=source_uri,
                        source_system=connector,
                        parser_profile=profile,
                    )
                    chunks = parse_document(tmp_path, ctx=ctx)
                    result = write_chunks(chunks)
                    chunk_total += result.get("validated", 0)
                    registry.mark_ingested(registry_key=key, etag=obj.etag)
                    ingested += 1
                finally:
                    tmp_path.unlink(missing_ok=True)
            except Exception as exc:  # noqa: BLE001 — per-file error isolation
                errors.append({"key": obj.key, "message": str(exc)})

    summary = {
        "status": "completed" if not errors else "completed_with_errors",
        "job_id": job_id,
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "version_id": version_id,
        "connector": connector,
        "mode": mode,
        "ingested": ingested,
        "skipped": skipped,
        "chunk_count": chunk_total,
        "files_done": ingested,
        "files_total": ingested + skipped,
        "error_count": len(errors),
        "errors": errors,
        "stub": getattr(connector_client, "is_stub", False),
    }
    publish_connector_sync(
        tenant_id=tenant_id,
        collection_id=collection_id,
        job_id=job_id,
        ingested=ingested,
    )
    publish_ingest_completed(
        tenant_id=tenant_id,
        collection_id=collection_id,
        job_id=job_id,
        chunk_count=chunk_total,
    )
    return summary
