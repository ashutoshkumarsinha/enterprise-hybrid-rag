#!/usr/bin/env python3
"""Emit a test span to the OTLP collector (validates IF-5 / observability stack)."""

from __future__ import annotations

import os
import sys

endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")
service = os.environ.get("OTEL_SERVICE_NAME", "hybrid-rag-synthetic")

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create({"service.name": service, "module_id": "synthetic"})
provider = TracerProvider(resource=resource)
insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=insecure)))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("synthetic")
with tracer.start_as_current_span("synthetic.healthcheck") as span:
    span.set_attribute("test", True)
    span.set_attribute("module_id", service)

provider.force_flush()
print(f"synthetic trace exported to {endpoint}")
