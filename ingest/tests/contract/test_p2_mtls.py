"""E-34 mTLS Caddy profile contract."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MTLS_DOC = REPO_ROOT / "infra" / "docs" / "MTLS.md"
MTLS_EXAMPLE = REPO_ROOT / "infra" / "caddy" / "Caddyfile.mtls.example"
RENDER_SCRIPT = REPO_ROOT / "infra" / "scripts" / "render_caddyfile.py"
GEN_CERTS = REPO_ROOT / "infra" / "scripts" / "gen_mtls_certs.sh"
INFRA_TOML = REPO_ROOT / "infra" / "config" / "infra.toml.example"


def test_mtls_docs_and_example_exist() -> None:
    assert MTLS_DOC.is_file()
    text = MTLS_DOC.read_text(encoding="utf-8")
    assert "E-34" in text
    assert "caddy.mtls" in text
    assert "Linkerd" in text or "service mesh" in text.lower()

    example = MTLS_EXAMPLE.read_text(encoding="utf-8")
    assert "tls_client_auth" in example
    assert example.count("flush_interval -1") >= 2


def test_render_caddyfile_emits_mtls_transport() -> None:
    mtls_toml = """\
[caddy]
proxy_mcp = true
site_name = "rag.example.com"
tls = true
email = "ops@example.com"
mcp_upstream = "https://query:8010"

[caddy.mtls]
enabled = true
upstream_ca = "/etc/caddy/certs/ca.crt"
upstream_cert = "/etc/caddy/certs/client.crt"
upstream_key = "/etc/caddy/certs/client.key"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(mtls_toml)
        cfg = Path(f.name)

    result = subprocess.run(
        [sys.executable, str(RENDER_SCRIPT), "--config", str(cfg)],
        capture_output=True,
        text=True,
        check=False,
    )
    cfg.unlink(missing_ok=True)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "tls_trust_pool file" in out
    assert "tls_client_auth" in out
    assert "flush_interval -1" in out


def test_gen_mtls_certs_script_produces_dev_layout() -> None:
    assert GEN_CERTS.is_file()
    with tempfile.TemporaryDirectory() as tmp:
        env = {"MTLS_CERT_DIR": tmp}
        result = subprocess.run(
            [str(GEN_CERTS)],
            capture_output=True,
            text=True,
            check=False,
            env={**dict(__import__("os").environ), **env},
        )
        assert result.returncode == 0, result.stderr
        out = Path(tmp)
        for name in ("ca.crt", "server.crt", "server.key", "caddy-client.crt", "client-ca.crt"):
            assert (out / name).is_file(), name
