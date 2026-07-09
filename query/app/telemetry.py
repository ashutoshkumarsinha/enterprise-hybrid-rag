"""OpenTelemetry bootstrap for hybrid-rag-query."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_CONFIGURED = False


def setup_otel(app: FastAPI | None = None) -> None:
    """Configure OTLP export and optional FastAPI auto-instrumentation."""
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

    service_name = os.environ.get("OTEL_SERVICE_NAME", "hybrid-rag-query")
    resource = Resource.create(
        {
            "service.name": service_name,
            "module_id": "hybrid-rag-query",
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

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/healthz,/",
        )

    _CONFIGURED = True


def get_tracer(name: str = "hybrid-rag-query"):
    from opentelemetry import trace

    return trace.get_tracer(name)
