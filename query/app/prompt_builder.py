"""Assemble LLM messages for grounded RAG answers.

Spec: §6.13 · FR-17 context token budget (truncation TBD).
"""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "You are an enterprise document research assistant. "
    "Answer using only the provided context. Cite sources inline when possible. "
    "If context is insufficient, say so clearly."
)


def build_chat_messages(state: dict[str, Any]) -> list[dict[str, str]]:
    """Build OpenAI-style messages from pipeline state."""
    context_blocks = state.get("context_blocks") or []
    if not context_blocks:
        chunks = state.get("retrieved_chunks") or []
        context_blocks = [c.get("text", "") for c in chunks if c.get("text")]

    context_text = "\n\n---\n\n".join(block for block in context_blocks if block)
    history = state.get("conversation_history") or []
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-10:]:
        role = turn.get("role", "user")
        if role in ("user", "assistant", "system"):
            messages.append({"role": role, "content": turn.get("content", "")})
    user_body = state.get("query", "")
    if context_text:
        user_body = f"Context:\n{context_text}\n\nQuestion: {user_body}"
    messages.append({"role": "user", "content": user_body})
    return messages
