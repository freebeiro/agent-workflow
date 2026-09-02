#!/usr/bin/env python3
"""Classify compact agent check-ins without loading agent context."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from checkin import validate
from registry import load

TERMINAL = {"DONE", "BLOCKED", "WAITING_INPUT", "SESSION_UNAVAILABLE"}
CONTROL_FILES = {"dispatcher-check-required.json"}


def inspect(directory: Path, timeout_minutes: float, registry: Path | None = None) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    identities = load(registry) if registry else {}
    states: list[dict[str, object]] = []
    invalid = 0
    for path in sorted(directory.glob("*.json")):
        if path.name in CONTROL_FILES:
            continue
        try:
            value = validate(json.loads(path.read_text(encoding="utf-8")))
            if value["status"] in TERMINAL:
                history = path.with_name(path.name + ".history.jsonl")
                if not history.exists() or '"status": "ACTIVE"' not in history.read_text(encoding="utf-8"):
                    raise ValueError("terminal state has no prior ACTIVE check-in")
            timestamp = datetime.fromisoformat(value["timestamp"].replace("Z", "+00:00"))
            age = (now - timestamp.astimezone(timezone.utc)).total_seconds()
            identity = identities.get(value["agent_id"], {})
            states.append({"file": path.name, "agent_id": value["agent_id"], "display_name": identity.get("display_name", value["agent_id"]), "role": identity.get("role", "unknown"), "provider": identity.get("provider", "unknown"), "session_id": identity.get("session_id", "unknown"), "task_id": value["task_id"], "status": value["status"], "age_seconds": round(age, 3)})
        except (OSError, ValueError, json.JSONDecodeError):
            invalid += 1
    timed_out = any(item["age_seconds"] > timeout_minutes * 60 for item in states if item["status"] == "ACTIVE")
    all_terminal = bool(states) and all(item["status"] in TERMINAL for item in states)
    if invalid:
        outcome = "INVALID_CHECKIN"
    elif timed_out:
        outcome = "TIMEOUT"
    elif all_terminal:
        outcome = "ACTIONABLE"
    else:
        outcome = "QUIET"
    return {"outcome": outcome, "agent_count": len(states), "valid_agent_count": len(states), "invalid_count": invalid, "invalid_file_count": invalid, "all_terminal": all_terminal, "timed_out": timed_out, "states": states}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--timeout-minutes", type=float, default=10.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--registry", type=Path, default=None)
    args = parser.parse_args()
    result = inspect(args.directory, args.timeout_minutes, args.registry)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(result["outcome"])
    return 0 if result["outcome"] != "INVALID_CHECKIN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
