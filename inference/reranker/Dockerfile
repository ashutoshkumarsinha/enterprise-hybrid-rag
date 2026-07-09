FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn sentence-transformers

COPY sidecar.py .

ENV PORT=8091
ENV RERANKER_MODEL=BAAI/bge-reranker-large

EXPOSE 8091
CMD ["python", "sidecar.py"]
