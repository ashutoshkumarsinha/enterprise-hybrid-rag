"""HTTP reranker client — inference CrossEncoder sidecar.

Spec: §6.5 · `POST /predict` on reranker sidecar.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class RerankerClient:
    """Score and reorder retrieved chunks."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        top_k: int | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("RERANKER_URL", "")).rstrip("/")
        self.top_k = top_k or int(os.environ.get("RERANK_TOP_K", "4"))
        self.timeout_s = timeout_s
        self._stub = os.environ.get("RERANKER_STUB", "").lower() in ("true", "1", "yes") or not self.base_url

    @property
    def is_stub(self) -> bool:
        return self._stub

    def healthcheck(self) -> bool:
        if self._stub:
            return True
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/healthz")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def rerank(
        self,
        query: str,
        chunks: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[float]]:
        if not chunks:
            return [], []
        if self._stub:
            scores = [float(c.get("score", 0.85)) for c in chunks]
            ranked = _sort_by_scores(chunks, scores, self.top_k)
            top_scores = [float(c.get("score", 0.0)) for c in ranked]
            return ranked, top_scores

        passages = [c.get("text", "") or c.get("title", "") or " " for c in chunks]
        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(
                f"{self.base_url}/predict",
                json={"query": query, "passages": passages},
            )
            response.raise_for_status()
            scores = [float(s) for s in response.json().get("scores", [])]
        if len(scores) < len(chunks):
            scores.extend([0.0] * (len(chunks) - len(scores)))
        ranked = _sort_by_scores(chunks, scores, self.top_k)
        top_scores = [float(c.get("score", 0.0)) for c in ranked]
        return ranked, top_scores


def _sort_by_scores(
    chunks: list[dict[str, Any]],
    scores: list[float],
    top_k: int,
) -> list[dict[str, Any]]:
    paired = list(zip(chunks, scores, strict=False))
    paired.sort(key=lambda item: item[1], reverse=True)
    ranked: list[dict[str, Any]] = []
    for chunk, score in paired[:top_k]:
        updated = dict(chunk)
        updated["score"] = score
        ranked.append(updated)
    return ranked
