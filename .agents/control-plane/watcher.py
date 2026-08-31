#!/usr/bin/env python3
"""Classify compact agent check-ins without loading agent context."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from checkin import validate

TERMINAL = {"DONE", "BLOCKED", "WAITING_INPUT", "SESSION_UNAVAILABLE"}


def inspect(directory: Path, timeout_minutes: float) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    states: list[dict[str, object]] = []
    invalid = 0
    for path in sorted(directory.glob("*.json")):
        try:
            value = validate(json.loads(path.read_text(encoding="utf-8")))
            timestamp = datetime.fromisoformat(value["timestamp"].replace("Z", "+00:00"))
            age = (now - timestamp.astimezone(timezone.utc)).total_seconds()
            states.append({"file": path.name, "agent_id": value["agent_id"], "task_id": value["task_id"], "status": value["status"], "age_seconds": round(age, 3)})
        except (OSError, ValueError, json.JSONDecodeError):
            invalid += 1
    timed_out = any(item["age_seconds"] > timeout_minutes * 60 for item in states if item["status"] == "ACTIVE")
    all_terminal = bool(states) and all(item["status"] in TERMINAL for item in states)
    if invalid:
        outcome = "INVALID"
    elif timed_out:
        outcome = "TIMEOUT"
    elif all_terminal:
        outcome = "ACTIONABLE"
    else:
        outcome = "QUIET"
    return {"outcome": outcome, "agent_count": len(states), "invalid_count": invalid, "all_terminal": all_terminal, "timed_out": timed_out, "states": states}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--timeout-minutes", type=float, default=10.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = inspect(args.directory, args.timeout_minutes)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(result["outcome"])
    return 0 if result["outcome"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
