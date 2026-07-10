"""Structured file parsers — JSON, YAML, CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.parsers.base import ParsedBlock


def parse_json_file(path: Path) -> list[ParsedBlock]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        blocks = []
        for idx, item in enumerate(data):
            blocks.append(
                ParsedBlock(
                    text=json.dumps(item, indent=2, ensure_ascii=False),
                    section_title=f"row-{idx}",
                    section_id=f"row-{idx}",
                    block_type="code",
                )
            )
        return blocks or [ParsedBlock(text="[]", block_type="code")]
    return [ParsedBlock(text=json.dumps(data, indent=2, ensure_ascii=False), block_type="code")]


def parse_csv_file(path: Path) -> list[ParsedBlock]:
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        blocks: list[ParsedBlock] = []
        for idx, row in enumerate(reader):
            lines = [f"{key}: {value}" for key, value in row.items() if value]
            blocks.append(
                ParsedBlock(
                    text="\n".join(lines),
                    section_title=f"row-{idx}",
                    section_id=f"row-{idx}",
                    block_type="table",
                )
            )
        return blocks or [ParsedBlock(text="(empty csv)", block_type="table")]


def parse_yaml_file(path: Path) -> list[ParsedBlock]:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("PyYAML required for .yaml parsing") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [ParsedBlock(text=json.dumps(data, indent=2, default=str), block_type="code")]
