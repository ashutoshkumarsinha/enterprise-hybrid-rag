"""INF-P4 Caddy SSE flush_interval contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CADDY_EXAMPLE = REPO_ROOT / "infra" / "caddy" / "Caddyfile.example"
RENDER_SCRIPT = REPO_ROOT / "infra" / "scripts" / "render_caddyfile.py"
INFRA_TOML = REPO_ROOT / "infra" / "config" / "infra.toml.example"


def test_caddyfile_example_disables_sse_buffering() -> None:
    text = CADDY_EXAMPLE.read_text(encoding="utf-8")
    assert text.count("flush_interval -1") >= 2
    assert "/mcp/*" in text
    assert "/research/stream" in text


def test_render_caddyfile_emits_sse_routes() -> None:
    result = subprocess.run(
        [sys.executable, str(RENDER_SCRIPT), "--config", str(INFRA_TOML)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert output.count("flush_interval -1") >= 2
    assert "handle_path /mcp/*" in output
    assert "handle /research/stream" in output
