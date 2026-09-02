#!/usr/bin/env python3
"""Register Codex worker identity without changing the compact check-in schema."""
from __future__ import annotations
import argparse, json
from pathlib import Path

FIELDS = ("session_id", "display_name", "role", "task_id", "parent_architect", "dispatcher")

def register(path: Path, values: dict[str, str]) -> None:
    if set(values) != set(FIELDS) or any(not str(v).strip() for v in values.values()):
        raise ValueError("registry entry requires: " + ", ".join(FIELDS))
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[values["session_id"]] = values
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def load(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        return {}
    aliases: dict[str, dict[str, str]] = {}
    for entry in value.values():
        if isinstance(entry, dict) and all(str(entry.get(field, "")).strip() for field in FIELDS):
            aliases[entry["session_id"]] = entry
            aliases[entry["display_name"]] = entry
    return aliases

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("path", type=Path)
    for field in FIELDS: p.add_argument("--" + field.replace("_", "-"), required=True)
    a = p.parse_args(); register(a.path, {f: getattr(a, f) for f in FIELDS}); return 0

if __name__ == "__main__": raise SystemExit(main())
