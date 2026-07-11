"""Langfuse headless-init + query/.env sync contract (IF-5)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENSURE = REPO_ROOT / "observability" / "scripts" / "ensure_langfuse_init.sh"
BOOTSTRAP = REPO_ROOT / "scripts" / "bootstrap_langfuse_keys.sh"
ENV_SET = REPO_ROOT / "scripts" / "env_set.py"
COMPOSE = REPO_ROOT / "observability" / "compose" / "docker-compose.yml"


def test_langfuse_bootstrap_scripts_exist() -> None:
    for path in (ENSURE, BOOTSTRAP, ENV_SET):
        assert path.is_file(), path


def test_compose_wires_langfuse_headless_init() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "LANGFUSE_INIT_ORG_ID" in text
    assert "LANGFUSE_INIT_PROJECT_PUBLIC_KEY" in text
    assert "LANGFUSE_INIT_PROJECT_SECRET_KEY" in text


def test_env_set_updates_dotenv_idempotently() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / ".env"
        env_path.write_text("FOO=bar\nLANGFUSE_PUBLIC_KEY=\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(ENV_SET), str(env_path), "LANGFUSE_PUBLIC_KEY", "pk-lf-test"],
            check=True,
        )
        text = env_path.read_text(encoding="utf-8")
        assert "LANGFUSE_PUBLIC_KEY=pk-lf-test" in text
        assert "FOO=bar" in text
        assert text.count("LANGFUSE_PUBLIC_KEY=") == 1


def test_ensure_and_bootstrap_sync_keys_to_query_env() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        obs = Path(tmp) / "observability"
        obs.mkdir()
        query = Path(tmp) / "query"
        query.mkdir()
        (obs / ".env.example").write_text(
            (REPO_ROOT / "observability" / ".env.example").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (query / ".env.example").write_text(
            (REPO_ROOT / "query" / ".env.example").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        env = {**dict(__import__("os").environ), "OBS_ENV_FILE": str(obs / ".env")}
        subprocess.run(["bash", str(ENSURE)], check=True, env=env)
        obs_env = (obs / ".env").read_text(encoding="utf-8")
        assert "LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-lf-" in obs_env
        assert "LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-lf-" in obs_env

        boot_env = {
            **env,
            "QUERY_ENV_FILE": str(query / ".env"),
            "OBS_ENV_FILE": str(obs / ".env"),
        }
        subprocess.run(["bash", str(BOOTSTRAP)], check=True, env=boot_env)
        query_env = (query / ".env").read_text(encoding="utf-8")
        assert "LANGFUSE_PUBLIC_KEY=pk-lf-" in query_env
        assert "LANGFUSE_SECRET_KEY=sk-lf-" in query_env
        assert "LANGFUSE_HOST=http://langfuse:3000" in query_env
