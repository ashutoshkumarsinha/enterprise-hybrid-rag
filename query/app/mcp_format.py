"""Stable markdown formatting for MCP research_documents responses.

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §7.8 — answer, Sources, telemetry footer order.
"""

from __future__ import annotations

from typing import Any

from app.rag_state import RAGState


def format_research_markdown(state: RAGState) -> str:
    answer = state.get("answer_text") or ""
    sources = state.get("sources") or []
    lines = [answer.rstrip(), "", "**Sources:**"]
    if sources:
        for idx, src in enumerate(sources, start=1):
            label = src.get("label") or src.get("title") or "source"
            score = src.get("score")
            suffix = f" (score {score:.2f})" if isinstance(score, (int, float)) else ""
            lines.append(f"{idx}. {label}{suffix}")
    else:
        lines.append("_No sources returned._")

    timings = state.get("timings_ms") or {}
    timing_bits = ", ".join(f"{k}={v}ms" for k, v in sorted(timings.items()))
    scope = state.get("collection_id") or "auto"
    doc = state.get("document_id") or "—"
    scope_mode = state.get("scope_source") or ("explicit" if state.get("explicit_scope") else "inferred")
    footer = (
        f"*🔍 **MCP Search Telemetry:** Resolved scope: {scope} / {doc} ({scope_mode}) | "
        f"Timings: {timing_bits or 'n/a'} | stub={state.get('stub', False)} | "
        f"abstained={state.get('abstained', False)}*"
    )
    lines.extend(["", "---", footer])
    return "\n".join(lines)
