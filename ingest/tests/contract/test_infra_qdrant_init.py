"""INF-P1 Qdrant INT8 quantization init contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INIT_DB = REPO_ROOT / "infra" / "scripts" / "init-db.sh"
ENV_EXAMPLE = REPO_ROOT / "infra" / ".env.example"


def test_init_db_supports_int8_quantization() -> None:
    text = INIT_DB.read_text(encoding="utf-8")
    assert "QDRANT_INT8_QUANTIZATION" in text
    assert "QDRANT_ON_DISK_PAYLOAD" in text
    assert "quantization_config" in text
    assert '"int8"' in text
    assert "PATCH" in text


def test_env_example_documents_qdrant_tuning() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "QDRANT_ON_DISK_PAYLOAD=true" in text
    assert "QDRANT_INT8_QUANTIZATION=false" in text
