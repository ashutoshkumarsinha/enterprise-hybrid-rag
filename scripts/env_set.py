#!/usr/bin/env python3
"""Set or update KEY=VALUE lines in a dotenv file (idempotent)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _format_value(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9._/@:+-]+", value or ""):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def set_env_var(path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    found = False
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        if not line or line.lstrip().startswith("#"):
            out.append(line)
            continue
        match = _LINE.match(line)
        if match and match.group(1) == key:
            out.append(f"{key}={_format_value(value)}")
            found = True
        else:
            out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={_format_value(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set KEY=VALUE in a dotenv file")
    parser.add_argument("path", type=Path)
    parser.add_argument("key")
    parser.add_argument("value")
    args = parser.parse_args(argv)
    set_env_var(args.path, args.key, args.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
