"""OTLP histogram metrics for ingest jobs — FR-40 / SigNoz."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

MODULE_ID = "hybrid-rag-ingest"

_stage_histogram: Any = None
_METRICS_CONFIGURED = False


def metrics_enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in ("true", "1", "yes"):
        return False
    exporter = os.environ.get("OTEL_METRICS_EXPORTER", "none").strip().lower()
    if exporter not in ("", "none"):
        return exporter in ("otlp", "otlp_grpc", "grpc")
    return os.environ.get("SIGNOZ_ENABLED", "").lower() in ("true", "1", "yes")


def setup_ingest_metrics() -> None:
    global _stage_histogram, _METRICS_CONFIGURED
    if _METRICS_CONFIGURED or not metrics_enabled():
        return
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return
    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", MODULE_ID),
                "module_id": MODULE_ID,
            }
        )
        insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
        exporter = OTLPMetricExporter(endpoint=endpoint, insecure=insecure)
        reader = PeriodicExportingMetricReader(exporter)
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        meter = metrics.get_meter(MODULE_ID)
        _stage_histogram = meter.create_histogram(
            "ingest_stage_ms",
            unit="ms",
            description="Ingest pipeline stage wall time",
        )
        _METRICS_CONFIGURED = True
    except Exception:
        return


def record_ingest_stage_ms(stage: str, ms: int, *, tenant_id: str | None = None) -> None:
    if _stage_histogram is None or ms < 0:
        return
    attrs: dict[str, str] = {"module_id": MODULE_ID, "stage": stage}
    if tenant_id:
        attrs["tenant_id"] = tenant_id
    _stage_histogram.record(ms, attributes=attrs)


@contextmanager
def ingest_stage_timer(stage: str, *, tenant_id: str | None = None) -> Iterator[None]:
    setup_ingest_metrics()
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = int((time.perf_counter() - start) * 1000)
        record_ingest_stage_ms(stage, elapsed, tenant_id=tenant_id)
