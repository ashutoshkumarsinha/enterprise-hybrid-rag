"""Assemble LLM context blocks with Neo4j lineage and cross-references.

Spec: §6.13.2 context block structure.
"""

from __future__ import annotations

from typing import Any

from app.clients.neo4j import Neo4jClient
from app.client_factory import get_neo4j_client


def format_context_block(chunk: dict[str, Any], graph_meta: dict[str, Any] | None = None) -> str:
    """Format one reranked chunk as a markdown context block."""
    graph_meta = graph_meta or {}
    collection_id = chunk.get("collection_id", "")
    document_id = chunk.get("document_id", "")
    section = chunk.get("section_title") or chunk.get("title") or ""
    score = chunk.get("score")
    score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
    header = f"##### [{collection_id} / {document_id}"
    if section:
        header += f" §{section}"
    header += f" | {section or 'Section'} | Score: {score_text}]"

    lines = [header]
    lineage = graph_meta.get("lineage") or []
    if lineage:
        lines.append(f"*Lineage:* `{' → '.join(lineage)}`")
    cross_refs = [r for r in (graph_meta.get("cross_refs") or []) if r]
    if cross_refs:
        lines.append(f"*Cross-references:* {', '.join(cross_refs)}")
    image_url = graph_meta.get("image_url") or chunk.get("image_url")
    if image_url:
        lines.append(f"🖼️ *Asset:* [{image_url}]({image_url})")
    text = chunk.get("text", "")
    lines.extend(["", "Raw Source Block Content:", text])
    return "\n".join(lines)


def build_context_blocks(
    chunks: list[dict[str, Any]],
    graph_by_uuid: dict[str, dict[str, Any]],
) -> list[str]:
    """Build ordered context blocks (highest rerank score first)."""
    blocks: list[str] = []
    for chunk in chunks:
        uuid = str(chunk.get("uuid", ""))
        meta = graph_by_uuid.get(uuid) if uuid else None
        blocks.append(format_context_block(chunk, meta))
    return blocks


def enrich_context_blocks(
    state: dict[str, Any],
    neo4j_client: Neo4jClient | None = None,
) -> list[str]:
    """Fetch graph metadata and format context blocks for the answer node."""
    chunks = list(state.get("retrieved_chunks") or [])
    if not chunks:
        return []
    client = neo4j_client or get_neo4j_client()
    graph_by_uuid = client.enrich_chunks(chunks, tenant_id=state.get("tenant_id", ""))
    return build_context_blocks(chunks, graph_by_uuid)
