"""OpenTelemetry bootstrap for hybrid-rag-ingest."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_CONFIGURED = False

# E-06 normative ingest span names — ENTERPRISE_HYBRID_RAG_SPEC.md §10.4
SPAN_JOB_BATCH_WRITE = "ingest.job.batch_write"
SPAN_PARSER_PARSE_FILE = "ingest.parser.parse_file"
SPAN_CONNECTOR_SYNC = "ingest.connector_sync"
SPAN_BEAT_CONNECTOR_SYNC = "ingest.beat.connector_sync"

INGEST_SPAN_CATALOG: frozenset[str] = frozenset(
    {
        SPAN_JOB_BATCH_WRITE,
        SPAN_PARSER_PARSE_FILE,
        SPAN_CONNECTOR_SYNC,
        SPAN_BEAT_CONNECTOR_SYNC,
    }
)


def setup_otel(app: FastAPI | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in ("true", "1", "yes"):
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = os.environ.get("OTEL_SERVICE_NAME", "hybrid-rag-ingest")
    resource = Resource.create(
        {
            "service.name": service_name,
            "module_id": "hybrid-rag-ingest",
            "deployment.environment": os.environ.get("DEPLOY_ENV", "dev"),
        }
    )

    provider = TracerProvider(resource=resource)
    insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="/admin/healthz")

    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()
    except Exception:
        pass

    _CONFIGURED = True


def get_tracer(name: str = "hybrid-rag-ingest"):
    from opentelemetry import trace

    return trace.get_tracer(name)
