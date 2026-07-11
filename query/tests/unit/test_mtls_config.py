"""mTLS listener configuration tests."""

from __future__ import annotations

import os

from app.tls_config import mtls_enabled, uvicorn_ssl_kwargs


def test_mtls_disabled_by_default() -> None:
    os.environ.pop("MCP_MTLS_ENABLED", None)
    assert mtls_enabled() is False
    assert uvicorn_ssl_kwargs() == {}


def test_mtls_requires_cert_paths(monkeypatch, tmp_path) -> None:
    cert = tmp_path / "server.crt"
    key = tmp_path / "server.key"
    cert.write_text("stub-cert")
    key.write_text("stub-key")
    monkeypatch.setenv("MCP_MTLS_ENABLED", "true")
    monkeypatch.setenv("MCP_TLS_CERT", str(cert))
    monkeypatch.setenv("MCP_TLS_KEY", str(key))
    kwargs = uvicorn_ssl_kwargs()
    assert kwargs["ssl_certfile"] == str(cert)
    assert kwargs["ssl_keyfile"] == str(key)
