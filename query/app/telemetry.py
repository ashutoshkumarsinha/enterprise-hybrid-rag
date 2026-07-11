"""OpenTelemetry bootstrap for hybrid-rag-query."""

from __future__ import annotations

import functools
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.trace import Span

_CONFIGURED = False
_BENCHMARK_EXPORTER: object | None = None

# E-06 normative span names — ENTERPRISE_HYBRID_RAG_SPEC.md §10.4
SPAN_MCP_SSE_CONNECT = "mcp.sse.connect"
SPAN_MCP_RESEARCH_DOCUMENTS = "mcp.research_documents"
SPAN_MCP_AUTHZ_CHECK = "mcp.authz.check"
SPAN_SESSION_LOAD_HISTORY = "session.load_history"
SPAN_SESSION_APPEND_TURN = "session.append_turn"
SPAN_HTTP_RESEARCH_STREAM = "http.research_stream"
SPAN_RAG_PIPELINE = "rag_pipeline"
SPAN_RAG_NODE_CHECK_CACHE = "rag.node.check_cache"
SPAN_RAG_NODE_SUPERVISOR = "rag.node.supervisor"
SPAN_RAG_NODE_EMBED = "rag.node.embed"
SPAN_RAG_NODE_SCOPE = "rag.node.scope"
SPAN_RAG_NODE_RETRIEVE = "rag.node.retrieve"
SPAN_RAG_NODE_RERANK = "rag.node.rerank"
SPAN_RAG_NODE_GRAPH = "rag.node.graph"
SPAN_RAG_NODE_ANSWER = "rag.node.answer"
SPAN_STORE_QDRANT_RETRIEVE = "store.qdrant.retrieve"
SPAN_STORE_NEO4J_READ = "store.neo4j.read"
SPAN_INFERENCE_EMBED = "inference.embed"
SPAN_INFERENCE_CHAT = "inference.chat"

QUERY_SPAN_CATALOG: frozenset[str] = frozenset(
    {
        SPAN_MCP_SSE_CONNECT,
        SPAN_MCP_RESEARCH_DOCUMENTS,
        SPAN_MCP_AUTHZ_CHECK,
        SPAN_SESSION_LOAD_HISTORY,
        SPAN_SESSION_APPEND_TURN,
        SPAN_HTTP_RESEARCH_STREAM,
        SPAN_RAG_PIPELINE,
        SPAN_RAG_NODE_CHECK_CACHE,
        SPAN_RAG_NODE_SUPERVISOR,
        SPAN_RAG_NODE_EMBED,
        SPAN_RAG_NODE_SCOPE,
        SPAN_RAG_NODE_RETRIEVE,
        SPAN_RAG_NODE_RERANK,
        SPAN_RAG_NODE_GRAPH,
        SPAN_RAG_NODE_ANSWER,
        SPAN_STORE_QDRANT_RETRIEVE,
        SPAN_STORE_NEO4J_READ,
        SPAN_INFERENCE_EMBED,
        SPAN_INFERENCE_CHAT,
    }
)

RAG_NODE_SPAN_BY_GRAPH_NODE: dict[str, str] = {
    "check_cache": SPAN_RAG_NODE_CHECK_CACHE,
    "supervisor": SPAN_RAG_NODE_SUPERVISOR,
    "embed": SPAN_RAG_NODE_EMBED,
    "scope": SPAN_RAG_NODE_SCOPE,
    "retrieve": SPAN_RAG_NODE_RETRIEVE,
    "rerank": SPAN_RAG_NODE_RERANK,
    "graph_enrich": SPAN_RAG_NODE_GRAPH,
    "answer": SPAN_RAG_NODE_ANSWER,
}

F = TypeVar("F", bound=Callable[..., Any])


def set_span_attributes(span: Span, attributes: dict[str, Any]) -> None:
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


@contextmanager
def start_span(name: str, /, **attributes: Any) -> Iterator[Span]:
    """Start a normative OTel span with optional attributes."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("module_id", "hybrid-rag-query")
        set_span_attributes(span, attributes)
        yield span


def _rag_node_attributes(state: dict[str, Any], result: dict[str, Any], span_name: str) -> dict[str, Any]:
    merged = {**state, **result}
    timings = merged.get("timings_ms") or {}
    attrs: dict[str, Any] = {}
    if span_name == SPAN_RAG_NODE_CHECK_CACHE:
        attrs["from_cache"] = bool(merged.get("from_cache"))
    elif span_name == SPAN_RAG_NODE_SUPERVISOR:
        attrs["scope_source"] = merged.get("scope_source")
    elif span_name == SPAN_RAG_NODE_EMBED:
        attrs["embed_ms"] = timings.get("embed")
    elif span_name == SPAN_RAG_NODE_SCOPE:
        attrs["scope_source"] = merged.get("scope_source")
    elif span_name == SPAN_RAG_NODE_RETRIEVE:
        chunks = merged.get("retrieved_chunks") or []
        attrs["chunk_count"] = len(chunks)
    elif span_name == SPAN_RAG_NODE_RERANK:
        attrs["abstained"] = bool(merged.get("abstained"))
    elif span_name == SPAN_RAG_NODE_GRAPH:
        attrs["graph_ms"] = timings.get("graph")
    elif span_name == SPAN_RAG_NODE_ANSWER:
        attrs["stub"] = bool(merged.get("stub"))
        attrs["context_tokens"] = merged.get("context_tokens")
    return {k: v for k, v in attrs.items() if v is not None}


def traced_rag_node(span_name: str) -> Callable[[F], F]:
    """Decorator for LangGraph node functions — emits ``rag.node.*`` spans."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            with start_span(span_name, tenant_id=state.get("tenant_id")) as span:
                result = fn(state) or {}
                set_span_attributes(span, _rag_node_attributes(state, result, span_name))
                return result

        return wrapper  # type: ignore[return-value]

    return decorator


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
