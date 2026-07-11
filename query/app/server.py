"""Uvicorn entrypoint with optional mTLS — E-34."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    from app.tls_config import mtls_enabled, uvicorn_ssl_kwargs

    port = int(os.environ.get("QUERY_PORT", "8010"))
    host = os.environ.get("QUERY_HOST", "0.0.0.0")
    ssl_kwargs = uvicorn_ssl_kwargs()
    uvicorn.run(
        "app.mcp_server:app",
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
