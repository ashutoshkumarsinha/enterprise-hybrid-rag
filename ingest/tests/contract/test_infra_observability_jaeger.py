"""OBS-P4 Jaeger Badger persistent storage compose contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = REPO_ROOT / "observability" / "compose" / "docker-compose.yml"
PERSIST_COMPOSE = REPO_ROOT / "observability" / "compose" / "docker-compose.jaeger-persist.yml"
MAKEFILE = REPO_ROOT / "observability" / "Makefile"
ENV_EXAMPLE = REPO_ROOT / "observability" / ".env.example"


def test_jaeger_compose_wires_badger_storage() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "jaeger-badger-data:" in text
    assert "SPAN_STORAGE_TYPE: ${JAEGER_STORAGE_TYPE:-memory}" in text
    assert "BADGER_EPHEMERAL: ${JAEGER_BADGER_EPHEMERAL:-true}" in text
    assert "BADGER_DIRECTORY_VALUE: /badger/data" in text
    assert "BADGER_SPAN_STORE_TTL: ${JAEGER_TRACE_RETENTION:-168h}" in text
    assert "jaeger-badger-data:/badger" in text


def test_jaeger_persist_profile_override() -> None:
    text = PERSIST_COMPOSE.read_text(encoding="utf-8")
    assert 'profiles: ["jaeger-persist"]' in text
    assert "SPAN_STORAGE_TYPE: badger" in text
    assert 'BADGER_EPHEMERAL: "false"' in text


def test_makefile_supports_jaeger_persist_profile() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "PROFILE),jaeger-persist)" in text
    assert "docker-compose.jaeger-persist.yml" in text
    assert "--profile jaeger-persist" in text


def test_env_example_documents_jaeger_retention() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "JAEGER_TRACE_RETENTION=168h" in text
    assert "PROFILE=jaeger-persist" in text
