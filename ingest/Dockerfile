FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/

ENV ORCHESTRATOR_PORT=8020
EXPOSE 8020

CMD ["uvicorn", "app.orchestrator:app", "--host", "0.0.0.0", "--port", "8020"]
