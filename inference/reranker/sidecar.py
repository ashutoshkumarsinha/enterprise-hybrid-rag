#!/usr/bin/env python3
"""Minimal CrossEncoder reranker HTTP sidecar for hybrid-rag-inference.

Usage:
  RERANKER_MODEL=BAAI/bge-reranker-large PORT=8091 python sidecar.py
  RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2 PORT=8092 python sidecar.py
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="hybrid-rag-reranker")
_model = None


class PredictRequest(BaseModel):
    query: str
    passages: list[str]


@app.on_event("startup")
def load_model() -> None:
    global _model
    from sentence_transformers import CrossEncoder

    name = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-large")
    _model = CrossEncoder(name)


@app.get("/healthz")
def healthz() -> dict:
    if _model is None:
        return {"status": "loading", "model_loaded": False}
    return {"status": "ok", "model_loaded": True}


@app.post("/predict")
def predict(body: PredictRequest) -> dict:
    if _model is None:
        return {"scores": []}
    pairs = [(body.query, p) for p in body.passages]
    scores = _model.predict(pairs)
    return {"scores": [float(s) for s in scores]}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8091"))
    uvicorn.run(app, host="0.0.0.0", port=port)
