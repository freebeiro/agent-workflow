#!/usr/bin/env python3
"""Detect actionable local Codex state without invoking a model or service."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import time

from dispatcher_wake import fingerprint, SIGNALS
from watcher import inspect


def run_once(directory: Path, signal_path: Path, marker: Path, timeout_minutes: float) -> dict[str, object]:
    result = inspect(directory, timeout_minutes)
    outcome = result["outcome"]
    current = fingerprint(directory, result) if outcome in SIGNALS else ""
    previous = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    emitted = bool(current and current != previous)
    if emitted:
        marker.parent.mkdir(parents=True, exist_ok=True)
        signal_path.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(current + "\n", encoding="utf-8")
        payload = {"event": "dispatcher_check_required", "reason": outcome.lower(), "created_at": datetime.now(timezone.utc).isoformat(), "summary": result}
        temporary = signal_path.with_suffix(signal_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(signal_path)
    return {"outcome": outcome, "emitted": emitted, "agent_count": result["agent_count"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--signal", type=Path, default=None)
    parser.add_argument("--marker", type=Path, default=None)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-minutes", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    signal = args.signal or args.directory / "dispatcher-check-required.json"
    marker = args.marker or args.directory / ".codex-watch-marker"
    while True:
        print(json.dumps(run_once(args.directory, signal, marker, args.timeout_minutes), sort_keys=True), flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
