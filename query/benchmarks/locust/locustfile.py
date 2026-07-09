"""Locust load test — POST /research/stream (SSE). Platform §13.1, TL-09."""

from __future__ import annotations

import json
import os

from locust import HttpUser, between, task

TENANT_ID = os.environ.get("TENANT_ID", "acme-corp")
COLLECTION_ID = os.environ.get("COLLECTION_ID", "payments-api")


class ResearchStreamUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task
    def research_stream(self) -> None:
        payload = {
            "query": "What is the API rate limit?",
            "tenant_id": TENANT_ID,
            "collection_id": COLLECTION_ID,
        }
        with self.client.post(
            "/research/stream",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            stream=True,
            catch_response=True,
            timeout=120,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status {response.status_code}")
                return
            body = response.text or ""
            if "telemetry" not in body and "token" not in body and "done" not in body:
                response.failure("missing SSE payload markers")
            else:
                response.success()
