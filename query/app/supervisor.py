"""Supervisor LLM — optional query rewrite and scope inference.

Spec: §6.7 · §6.10 · inference/docs/CHAT_LLM.md supervisor role.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from app.clients.chat import ChatClient

SUPERVISOR_SYSTEM_PROMPT = """You are a search supervisor for an enterprise document RAG system.
Rewrite the user question into a standalone search query suitable for hybrid retrieval.
If the question is already clear, return it unchanged.

When you can infer document scope from the question, include JSON fields:
- rewritten_query (string, required)
- collection_id (string, optional)
- document_id (string, optional)
- confidence (number 0-1, optional)

Respond with JSON only. No markdown fences."""


def supervisor_enabled() -> bool:
    from app.settings import get_settings

    return get_settings().supervisor_enabled


def history_aware_supervisor() -> bool:
    from app.settings import get_settings

    return get_settings().history_aware_supervisor


def inference_threshold() -> float:
    return float(os.environ.get("SCOPE_INFERENCE_THRESHOLD", "0.7"))


def should_run_supervisor(state: dict[str, Any]) -> bool:
    if not supervisor_enabled():
        return False
    if state.get("skip_supervisor"):
        return False
    if state.get("explicit_scope"):
        return False
    return bool(state.get("query", "").strip())


def build_supervisor_messages(state: dict[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT}]
    if history_aware_supervisor():
        for turn in (state.get("conversation_history") or [])[-4:]:
            role = turn.get("role")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": turn.get("content", "")})
    tenant = state.get("tenant_id", "")
    collection = state.get("collection_id", "")
    user_prompt = f"Tenant: {tenant}\n"
    if collection:
        user_prompt += f"Pinned collection: {collection}\n"
    user_prompt += f"User question: {state.get('query', '')}"
    messages.append({"role": "user", "content": user_prompt})
    return messages


def parse_supervisor_response(text: str, *, original_query: str) -> dict[str, Any]:
    """Parse supervisor JSON; fall back to raw text or original query."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"query": cleaned or original_query, "scope_source": "inferred"}
    rewritten = (
        data.get("rewritten_query")
        or data.get("search_query")
        or data.get("query")
        or original_query
    )
    result: dict[str, Any] = {
        "query": str(rewritten).strip() or original_query,
        "scope_source": "inferred",
    }
    confidence = data.get("confidence")
    if confidence is not None:
        try:
            result["inference_score"] = float(confidence)
        except (TypeError, ValueError):
            pass
    if data.get("collection_id"):
        result["collection_id"] = str(data["collection_id"])
    if data.get("document_id"):
        result["document_id"] = str(data["document_id"])
    return result


def stub_supervise(state: dict[str, Any]) -> dict[str, Any]:
    """Deterministic supervisor for offline tests."""
    query = state.get("query", "")
    history = state.get("conversation_history") or []
    if history_aware_supervisor() and re.search(r"\b(it|that|those|they)\b", query, re.I):
        last_user = next(
            (turn.get("content", "") for turn in reversed(history) if turn.get("role") == "user"),
            "",
        )
        if last_user:
            return {
                "query": f"{last_user.rstrip('?')} — {query}",
                "scope_source": "inferred",
                "inference_score": 0.8,
            }
    visual_terms = ("diagram", "flowchart", "screenshot", "figure")
    updates: dict[str, Any] = {"query": query, "scope_source": "inferred"}
    if any(term in query.lower() for term in visual_terms):
        updates["visual_intent"] = True
    return updates


def supervise_query(state: dict[str, Any], chat: ChatClient) -> dict[str, Any]:
    """Run supervisor LLM and return partial state updates."""
    original = state.get("query", "")
    if chat.is_stub:
        return stub_supervise(state)

    max_tokens = int(os.environ.get("SUPERVISOR_MAX_TOKENS", "256"))
    messages = build_supervisor_messages(state)
    text, _ = chat.complete_messages(messages, max_tokens=max_tokens)
    parsed = parse_supervisor_response(text, original_query=original)
    parsed["original_query"] = original
    score = parsed.get("inference_score")
    if score is not None and score < inference_threshold():
        parsed.pop("collection_id", None)
        parsed.pop("document_id", None)
    return parsed
