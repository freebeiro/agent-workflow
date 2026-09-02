#!/usr/bin/env python3
"""Verify that the active project runtime resolves to this control plane."""
from __future__ import annotations

import argparse
from pathlib import Path

FILES = ("checkin.py", "watcher.py", "dispatcher_wake.py", "registry.py")


def check(source: Path, runtime: Path, state: Path) -> list[str]:
    errors: list[str] = []
    if state.is_symlink():
        errors.append(f"state must not be a symlink: {state}")
    if not state.is_dir():
        errors.append(f"state directory missing: {state}")
    for name in FILES:
        expected = source / name
        actual = runtime / name
        if not expected.is_file():
            errors.append(f"source file missing: {expected}")
            continue
        if not actual.is_symlink():
            errors.append(f"runtime file is not a symlink: {actual}")
            continue
        if not actual.exists():
            errors.append(f"broken symlink: {actual}")
            continue
        if actual.resolve() != expected.resolve():
            errors.append(f"symlink points elsewhere: {actual} -> {actual.resolve()}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    errors = check(args.source, args.runtime, args.state)
    if errors:
        print("CONTROL_PLANE_UNHEALTHY")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"CONTROL_PLANE_HEALTHY source={args.source} runtime={args.runtime} state={args.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
