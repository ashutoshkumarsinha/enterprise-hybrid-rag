"""OpenTelemetry bootstrap for hybrid-rag-query."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_CONFIGURED = False
_BENCHMARK_EXPORTER: object | None = None


def reset_otel() -> None:
    """Reset OTel SDK state (for benchmark A/B runs)."""
    global _CONFIGURED, _BENCHMARK_EXPORTER
    _CONFIGURED = False
    _BENCHMARK_EXPORTER = None
    from app.otel_metrics import reset_otel_metrics

    reset_otel_metrics()
    from opentelemetry import trace
    from opentelemetry.trace import NoOpTracerProvider

    trace.set_tracer_provider(NoOpTracerProvider())


def is_otel_configured() -> bool:
    return _CONFIGURED


def setup_otel_benchmark() -> None:
    """Configure in-process OTel with in-memory export (OBS-P3 overhead probe)."""
    global _CONFIGURED, _BENCHMARK_EXPORTER
    reset_otel()
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    _BENCHMARK_EXPORTER = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_BENCHMARK_EXPORTER))
    trace.set_tracer_provider(provider)
    _CONFIGURED = True


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
    from app.otel_metrics import setup_otel_metrics

    setup_otel_metrics()


def get_tracer(name: str = "hybrid-rag-query"):
    from opentelemetry import trace

    return trace.get_tracer(name)
