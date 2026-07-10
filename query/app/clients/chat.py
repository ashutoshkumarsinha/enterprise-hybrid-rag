"""OpenAI-compatible chat client for hybrid-rag-inference (vLLM).

Spec: IF-4 · LG-2 streaming answer node.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Iterator

import httpx

from app.prompt_builder import build_chat_messages


class ChatClient:
    """Chat completions against vLLM or deterministic stub text."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("VLLM_URL", "")).rstrip("/")
        self.model = model or os.environ.get("CHAT_LLM_MODEL", "meta-llama/Llama-3.2-3B-Instruct")
        self.max_tokens = max_tokens or int(os.environ.get("MAX_ANSWER_TOKENS", "2048"))
        self.timeout_s = timeout_s
        self._stub = os.environ.get("CHAT_STUB", "").lower() in ("true", "1", "yes") or not self.base_url

    @property
    def is_stub(self) -> bool:
        return self._stub

    def healthcheck(self) -> bool:
        if self._stub:
            return True
        try:
            root = self.base_url.removesuffix("/v1")
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{root}/v1/models")
                return response.status_code < 500
        except httpx.HTTPError:
            return False

    def complete(self, state: dict) -> tuple[str, bool]:
        """Return (answer_text, is_stub)."""
        messages = build_chat_messages(state)
        return self.complete_messages(messages, max_tokens=self.max_tokens)

    def complete_messages(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> tuple[str, bool]:
        """Blocking chat completion for arbitrary message lists (supervisor, etc.)."""
        if self._stub:
            user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return _stub_answer([{"role": "user", "content": user}]), True
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        text = data["choices"][0]["message"]["content"]
        return text, False

    async def stream_tokens(self, state: dict) -> AsyncIterator[str]:
        messages = build_chat_messages(state)
        if self._stub:
            text = _stub_answer(messages)
            for part in _split_stream_chunks(text):
                yield part
            return
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk["choices"][0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        yield text


def _stub_answer(messages: list[dict[str, str]]) -> str:
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if user.startswith("Context:"):
        _, _, question = user.partition("Question: ")
        query = question.strip() or user
    else:
        query = user
    return f"Stub grounded answer for: {query[:200]}"


def _split_stream_chunks(text: str) -> Iterator[str]:
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word if i == 0 else f" {word}"
