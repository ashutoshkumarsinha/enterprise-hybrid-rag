"""OTLP histogram metrics for FR-40 / SigNoz (rag_ttft_ms, rag_stage_ms)."""

from __future__ import annotations

import os
from typing import Any

MODULE_ID = "hybrid-rag-query"

_meter: Any = None
_ttft_histogram: Any = None
_stage_histogram: Any = None
_metric_reader: Any = None
_METRICS_CONFIGURED = False


def metrics_enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in ("true", "1", "yes"):
        return False
    exporter = os.environ.get("OTEL_METRICS_EXPORTER", "none").strip().lower()
    if exporter not in ("", "none"):
        return exporter in ("otlp", "otlp_grpc", "grpc")
    return os.environ.get("SIGNOZ_ENABLED", "").lower() in ("true", "1", "yes")


def is_otel_metrics_configured() -> bool:
    return _METRICS_CONFIGURED


def reset_otel_metrics() -> None:
    global _meter, _ttft_histogram, _stage_histogram, _metric_reader, _METRICS_CONFIGURED
    _meter = None
    _ttft_histogram = None
    _stage_histogram = None
    _metric_reader = None
    _METRICS_CONFIGURED = False
    try:
        from opentelemetry import metrics
        from opentelemetry.metrics import NoOpMeterProvider

        metrics.set_meter_provider(NoOpMeterProvider())
    except Exception:
        pass


def setup_otel_metrics(*, in_memory: bool = False) -> None:
    """Configure OTLP or in-memory histogram export for RAG latency metrics."""
    global _meter, _ttft_histogram, _stage_histogram, _metric_reader, _METRICS_CONFIGURED
    if _METRICS_CONFIGURED:
        return
    if not in_memory and not metrics_enabled():
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not in_memory and not endpoint:
        return

    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", MODULE_ID),
            "module_id": MODULE_ID,
            "deployment.environment": os.environ.get("DEPLOY_ENV", "dev"),
        }
    )

    if in_memory:
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader

        _metric_reader = InMemoryMetricReader()
        provider = MeterProvider(resource=resource, metric_readers=[_metric_reader])
    else:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
        exporter = OTLPMetricExporter(endpoint=endpoint, insecure=insecure)
        reader = PeriodicExportingMetricReader(exporter)
        provider = MeterProvider(resource=resource, metric_readers=[reader])

    metrics.set_meter_provider(provider)
    _meter = metrics.get_meter(MODULE_ID)
    _ttft_histogram = _meter.create_histogram(
        "rag_ttft_ms",
        unit="ms",
        description="Time to first streamed answer token",
    )
    _stage_histogram = _meter.create_histogram(
        "rag_stage_ms",
        unit="ms",
        description="RAG pipeline stage wall time",
    )
    _METRICS_CONFIGURED = True


def _base_attributes(*, tenant_id: str | None) -> dict[str, str]:
    attrs = {"module_id": MODULE_ID}
    if tenant_id and os.environ.get("OTEL_METRICS_TENANT_LABELS", "").lower() in ("true", "1", "yes"):
        attrs["tenant_id"] = tenant_id
    return attrs


def record_rag_stage_ms(stage: str, ms: int, *, tenant_id: str | None = None) -> None:
    if _stage_histogram is None or ms < 0:
        return
    attrs = _base_attributes(tenant_id=tenant_id)
    attrs["stage"] = stage
    _stage_histogram.record(ms, attributes=attrs)


def record_rag_ttft_ms(ms: int, *, tenant_id: str | None = None) -> None:
    if _ttft_histogram is None or ms < 0:
        return
    _ttft_histogram.record(ms, attributes=_base_attributes(tenant_id=tenant_id))


def record_pipeline_timings(timings_ms: dict[str, int] | None, *, tenant_id: str | None = None) -> None:
    for stage, value in (timings_ms or {}).items():
        if stage:
            record_rag_stage_ms(stage, int(value), tenant_id=tenant_id)


def metric_reader_snapshot() -> Any | None:
    """Return raw MetricsData from the in-memory reader (tests only)."""
    if _metric_reader is None:
        return None
    return _metric_reader.collect()
