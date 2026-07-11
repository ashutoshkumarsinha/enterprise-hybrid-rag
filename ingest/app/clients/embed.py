"""OpenAI-compatible embedding client for ingest-time dense vectors."""

from __future__ import annotations

import hashlib
import os
from typing import Any

import httpx


class EmbedClient:
    """Embed chunk text via hybrid-rag-inference or deterministic stub vectors."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("VLLM_EMBED_URL", "")).rstrip("/")
        self.model = model or os.environ.get("EMBED_MODEL", "intfloat/e5-base-v2")
        self.dimension = dimension or int(os.environ.get("EMBED_DIMENSION", "768"))
        self.timeout_s = timeout_s
        self._stub = os.environ.get("EMBED_STUB", "").lower() in ("true", "1", "yes") or not self.base_url

    @property
    def is_stub(self) -> bool:
        return self._stub

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._stub:
            return [_stub_dense_vector(text, self.dimension) for text in texts]
        payload = {"model": self.model, "input": texts}
        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(f"{self.base_url}/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()
        vectors = [item["embedding"] for item in data["data"]]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(f"embed dimension mismatch: got {len(vector)}, expected {self.dimension}")
        return vectors

    def sparse_from_text(self, text: str) -> dict[str, Any]:
        """Hash-token sparse representation for Qdrant ``bm25-text`` (spec §4.5)."""
        tokens = [t for t in text.lower().split() if t]
        if not tokens:
            return {"indices": [0], "values": [1.0]}
        indices: list[int] = []
        values: list[float] = []
        for token in tokens:
            idx = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % 100_000
            indices.append(idx)
            values.append(1.0)
        return {"indices": indices, "values": values}

    def healthcheck(self) -> bool:
        if self._stub:
            return True
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url.replace('/v1', '')}/models")
                return response.status_code < 500
        except httpx.HTTPError:
            return False


def _stub_dense_vector(text: str, dimension: int) -> list[float]:
    """Deterministic pseudo-embedding for offline tests."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    while len(out) < dimension:
        for byte in seed:
            out.append((byte / 255.0) * 2.0 - 1.0)
            if len(out) >= dimension:
                break
        seed = hashlib.sha256(seed).digest()
    return out
