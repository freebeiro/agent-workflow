#!/usr/bin/env python3
"""Write and validate compact durable agent check-ins."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

STATUSES = {"DONE", "BLOCKED", "WAITING_INPUT", "ACTIVE", "SESSION_UNAVAILABLE"}
FIELDS = ("agent_id", "task_id", "status", "timestamp", "next_action", "eta", "report_ref")


def validate(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise ValueError("check-in must contain exactly: " + ", ".join(FIELDS))
    if any(not isinstance(value[key], str) or not value[key].strip() for key in FIELDS):
        raise ValueError("all check-in fields must be non-empty strings")
    if value["status"] not in STATUSES:
        raise ValueError("invalid status: " + value["status"])
    datetime.fromisoformat(value["timestamp"].replace("Z", "+00:00"))
    return value


def write_checkin(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(validate(values), sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    for field in FIELDS:
        parser.add_argument("--" + field.replace("_", "-"), required=True)
    args = parser.parse_args()
    values = {field: getattr(args, field) for field in FIELDS}
    write_checkin(args.path, values)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
