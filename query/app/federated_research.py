"""Federated research merge across regional MCP query nodes — E-32 research path."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

from app.federated_catalog import (
    federated_mcp_enabled,
    mcp_region,
    peer_endpoints,
    tenant_home_region,
)
from app.models import AuthContext
from app.tls_config import peer_ssl_context


def federated_research_enabled() -> bool:
    if not federated_mcp_enabled():
        return False
    return os.environ.get("FEDERATED_RESEARCH_ENABLED", "true").lower() in ("true", "1", "yes")


def _service_token() -> str:
    return os.environ.get("FEDERATED_MCP_SERVICE_TOKEN", "")


def _peer_request(
    url: str,
    body: dict[str, Any],
    *,
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    if os.environ.get("FEDERATED_MCP_STUB", "").lower() in ("true", "1", "yes"):
        return None
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = _service_token()
    if token:
        headers["X-Federated-Service-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    ctx = peer_ssl_context()
    try:
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx) if ctx else urllib.request.HTTPHandler()
        )
        with opener.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ssl.SSLError):
        return None
    return payload if isinstance(payload, dict) else None


def fetch_peer_research(
    base_url: str,
    args: dict[str, Any],
    *,
    tenant_id: str,
) -> dict[str, Any] | None:
    """Call peer ``research_documents`` with structured federated response."""
    body = {
        k: v
        for k, v in args.items()
        if k not in ("session_id", "create_session_if_missing", "federated_internal")
    }
    body["tenant_id"] = tenant_id
    body["federated_internal"] = True
    url = f"{base_url.rstrip('/')}/mcp/tools/research_documents"
    payload = _peer_request(url, body)
    if not payload:
        return None
    return {
        "region": None,
        "markdown": payload.get("markdown", ""),
        "answer_text": payload.get("answer_text", ""),
        "sources": payload.get("sources") or [],
        "stub": payload.get("stub", True),
    }


def merge_research_results(
    local: dict[str, Any],
    peer_results: list[dict[str, Any]],
    *,
    home_region: str | None,
    local_region: str,
) -> dict[str, Any]:
    """Merge local RAG state with peer regional answers and sources."""
    sources = list(local.get("sources") or [])
    seen = {(s.get("document_id"), s.get("version_id")) for s in sources if isinstance(s, dict)}

    for peer in peer_results:
        region = peer.get("region") or "peer"
        for src in peer.get("sources") or []:
            if not isinstance(src, dict):
                continue
            key = (src.get("document_id"), src.get("version_id"))
            if key not in seen:
                tagged = {**src, "region": region}
                sources.append(tagged)
                seen.add(key)

    answer = local.get("answer_text", "")
    if home_region and home_region != local_region:
        for peer in peer_results:
            if peer.get("region") == home_region and peer.get("answer_text"):
                answer = peer["answer_text"]
                break

    if peer_results and os.environ.get("FEDERATED_RESEARCH_APPEND", "").lower() in (
        "true",
        "1",
        "yes",
    ):
        blocks = [
            f"### Region {p.get('region', 'peer')}\n{p.get('answer_text', '').strip()}"
            for p in peer_results
            if p.get("answer_text")
        ]
        if blocks:
            answer = f"{answer.rstrip()}\n\n---\n\n" + "\n\n".join(blocks)

    regions = [local_region] + [p.get("region") for p in peer_results if p.get("region")]
    merged = {**local, "answer_text": answer, "sources": sources, "federated_regions": regions}
    return merged


async def merge_federated_research(
    local_final: dict[str, Any],
    args: dict[str, Any],
    *,
    ctx: AuthContext,
) -> dict[str, Any]:
    """Fan-out to peer regions and merge structured research results."""
    if args.get("federated_internal") or not federated_research_enabled():
        return local_final

    peers = peer_endpoints()
    if not peers:
        return local_final

    tenant_id = args.get("tenant_id") or ctx.tenant_id
    home = tenant_home_region(tenant_id)
    local_region = mcp_region()
    peer_order = sorted(
        peers.items(),
        key=lambda item: 0 if home and item[0] == home else 1,
    )

    peer_results: list[dict[str, Any]] = []
    for region, base_url in peer_order:
        if region == local_region:
            continue
        result = fetch_peer_research(base_url, args, tenant_id=tenant_id)
        if result:
            result["region"] = region
            peer_results.append(result)

    if not peer_results:
        return local_final

    return merge_research_results(
        local_final,
        peer_results,
        home_region=home,
        local_region=local_region,
    )
