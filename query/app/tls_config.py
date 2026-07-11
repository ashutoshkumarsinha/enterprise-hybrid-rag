"""mTLS configuration for hybrid-rag-query MCP HTTP listener — E-34."""

from __future__ import annotations

import os
import ssl
from pathlib import Path
from typing import Any


def mtls_enabled() -> bool:
    return os.environ.get("MCP_MTLS_ENABLED", "").lower() in ("true", "1", "yes")


def _path(name: str) -> str | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    path = Path(raw)
    return str(path) if path.is_file() else raw


def uvicorn_ssl_kwargs() -> dict[str, Any]:
    """Keyword args for ``uvicorn.run`` when terminating TLS on :8010."""
    if not mtls_enabled():
        return {}
    cert = _path("MCP_TLS_CERT")
    key = _path("MCP_TLS_KEY")
    if not cert or not key:
        raise RuntimeError("MCP_MTLS_ENABLED requires MCP_TLS_CERT and MCP_TLS_KEY")
    kwargs: dict[str, Any] = {
        "ssl_certfile": cert,
        "ssl_keyfile": key,
    }
    client_ca = _path("MCP_TLS_CLIENT_CA")
    if client_ca:
        kwargs["ssl_ca_certs"] = client_ca
        kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED
    return kwargs


def peer_ssl_context() -> ssl.SSLContext | None:
    """Client SSL context for federated peer calls (Caddy → query mTLS)."""
    cert = _path("MCP_TLS_CLIENT_CERT") or _path("MCP_TLS_CERT")
    key = _path("MCP_TLS_CLIENT_KEY") or _path("MCP_TLS_KEY")
    ca = _path("MCP_TLS_PEER_CA") or _path("MCP_TLS_CLIENT_CA")
    if not cert or not key:
        return None
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.load_cert_chain(cert, key)
    if ca:
        ctx.load_verify_locations(ca)
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def public_base_url() -> str:
    if mtls_enabled():
        host = os.environ.get("QUERY_PUBLIC_HOST", "127.0.0.1")
        port = os.environ.get("QUERY_PORT", "8010")
        return f"https://{host}:{port}"
    port = os.environ.get("QUERY_PORT", "8010")
    return os.environ.get("QUERY_BASE_URL", f"http://127.0.0.1:{port}")
