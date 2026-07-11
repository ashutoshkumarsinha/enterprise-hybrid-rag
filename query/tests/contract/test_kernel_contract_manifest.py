"""E-15 SHARED_CONTRACTS.md §14 kernel contract test manifest."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Normative PR-tier contract tests from modules/SHARED_CONTRACTS.md §14
KERNEL_CONTRACT_TESTS: dict[str, str] = {
    "test_chunk_payload_schema.py": "ingest/tests/contract/test_chunk_payload_schema.py",
    "test_event_cache_bump.py": "query/tests/contract/test_event_cache_bump.py",
    "test_catalog_ro_role.py": "query/tests/contract/test_catalog_ro_role.py",
    "test_research_documents_markdown.py": "query/tests/contract/test_research_documents_markdown.py",
    "test_sse_event_contract.py": "query/tests/contract/test_sse_event_contract.py",
    "test_schema_coverage.py": "query/tests/contract/test_schema_coverage.py",
}


def test_kernel_contract_tests_exist_on_disk() -> None:
    missing = [
        rel for rel in KERNEL_CONTRACT_TESTS.values() if not (REPO_ROOT / rel).is_file()
    ]
    assert not missing, f"missing kernel contract tests: {missing}"
