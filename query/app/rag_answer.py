"""Answer assembly helpers shared by graph node and SSE streaming."""

from __future__ import annotations

import time
from typing import Any

from app.rag_state import RAGState


def build_sources(state: RAGState) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for chunk in state.get("retrieved_chunks") or []:
        sources.append(
            {
                "label": chunk.get("label")
                or f"{chunk.get('collection_id', '')} / {chunk.get('document_id', '')}",
                "document_id": chunk.get("document_id"),
                "collection_id": chunk.get("collection_id"),
                "score": chunk.get("score"),
            }
        )
    return sources


def answer_updates(state: RAGState, answer_text: str, *, stub: bool) -> dict[str, Any]:
    start = time.perf_counter()
    timings = dict(state.get("timings_ms") or {})
    timings["answer"] = int((time.perf_counter() - start) * 1000)
    return {
        "answer_text": answer_text,
        "sources": build_sources(state),
        "stub": stub,
        "timings_ms": timings,
    }
