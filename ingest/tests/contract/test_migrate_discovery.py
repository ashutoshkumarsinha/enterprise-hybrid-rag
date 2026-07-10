"""Migration runner file discovery."""

from __future__ import annotations

from pathlib import Path

from app.migrate import pending_files


def test_pending_files_sorted() -> None:
    applied = set()
    pending = pending_files(applied)
    names = [p.name for p in pending]
    assert names == sorted(names)
    assert any("001_catalog" in n for n in names)
