#!/usr/bin/env python3
"""Poll local check-ins and resume a Dispatcher only on a new signal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from watcher import inspect
from watcher import CONTROL_FILES

SIGNALS = {"ACTIONABLE", "TIMEOUT", "INVALID"}
TERMINAL = {"DONE", "BLOCKED", "WAITING_INPUT", "SESSION_UNAVAILABLE"}


def fingerprint(directory: Path, result: dict[str, object]) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.json")):
        if path.name in CONTROL_FILES:
            continue
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    digest.update(str(result["outcome"]).encode())
    return digest.hexdigest()


def consume_terminal(directory: Path) -> None:
    """Remove only terminal presence files after the Dispatcher was queued."""
    for path in directory.glob("*.json"):
        if path.name in CONTROL_FILES:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("status") in TERMINAL:
            path.unlink(missing_ok=True)


def run_once(directory: Path, timeout_minutes: float, marker: Path, command: list[str], dry_run: bool) -> dict[str, object]:
    result = inspect(directory, timeout_minutes)
    signal = result["outcome"] in SIGNALS
    current = fingerprint(directory, result) if signal else ""
    previous = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    triggered = bool(signal and current != previous)
    if triggered:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(current + "\n", encoding="utf-8")
        if not dry_run:
            message = command[-1] + "\n" + json.dumps(result, sort_keys=True)
            subprocess.run(command[:-1] + [message], check=True)
            consume_terminal(directory)
    states = result["states"]
    return {"outcome": result["outcome"], "triggered": triggered, "agent_count": result["agent_count"],
            "working": [item for item in states if item["status"] == "ACTIVE"],
            "terminal": [item for item in states if item["status"] != "ACTIVE"],
            "agents": states}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-minutes", type=float, default=10.0)
    parser.add_argument("--marker", type=Path, default=None)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    marker = args.marker or args.directory / ".dispatcher-wake"
    # Queue through the local app-server daemon so the exact existing task is
    # targeted without opening a second interactive session.
    codex_bin = os.environ.get("CODEX_BIN", "codex")
    command = [codex_bin, "queue", "--thread", args.session_id, "--message", "Check compact control-plane signal:"]
    while True:
        print(json.dumps(run_once(args.directory, args.timeout_minutes, marker, command, args.dry_run), sort_keys=True), flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
