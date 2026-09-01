import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from checkin import validate, write_checkin
from watcher import inspect
from dispatcher_wake import run_once
from codex_watch import run_once as watch_once


def state(status="ACTIVE", timestamp=None):
    return {"agent_id": "agent-1", "task_id": "task-1", "status": status,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "next_action": "continue", "eta": "2m", "report_ref": "reports/task-1.md"}


class WatcherTests(unittest.TestCase):
    def test_checkin_has_exact_compact_schema(self):
        value = state()
        self.assertEqual(validate(value), value)
        with self.assertRaises(ValueError):
            validate({**value, "extra": "no"})

    def test_active_agents_are_quiet(self):
        with tempfile.TemporaryDirectory() as root:
            write_checkin(Path(root) / "agent.json", state())
            self.assertEqual(inspect(Path(root), 10)["outcome"], "QUIET")

    def test_all_terminal_agents_are_actionable(self):
        with tempfile.TemporaryDirectory() as root:
            write_checkin(Path(root) / "agent.json", state("DONE"))
            self.assertEqual(inspect(Path(root), 10)["outcome"], "ACTIONABLE")

    def test_stale_active_agent_times_out(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        with tempfile.TemporaryDirectory() as root:
            write_checkin(Path(root) / "agent.json", state(timestamp=old))
            self.assertEqual(inspect(Path(root), 10)["outcome"], "TIMEOUT")

    def test_idle_is_not_progress(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "agent.json").write_text(json.dumps({"status": "IDLE"}))
            result = inspect(Path(root), 10)
            self.assertEqual(result["outcome"], "INVALID")

    def test_dispatcher_wake_is_deduplicated_and_dry_run(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "states"
            marker = Path(root) / "marker"
            directory.mkdir()
            write_checkin(directory / "agent.json", state("DONE"))
            first = run_once(directory, 10, marker, ["false"], True)
            second = run_once(directory, 10, marker, ["false"], True)
            self.assertTrue(first["triggered"])
            self.assertFalse(second["triggered"])

    def test_local_watch_emits_signal_once_per_actionable_change(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "states"
            directory.mkdir()
            signal = Path(root) / "signal.json"
            marker = Path(root) / "marker"
            write_checkin(directory / "agent.json", state("DONE"))
            first = watch_once(directory, signal, marker, 10)
            second = watch_once(directory, signal, marker, 10)
            self.assertTrue(first["emitted"])
            self.assertFalse(second["emitted"])
            self.assertEqual(json.loads(signal.read_text())["event"], "dispatcher_check_required")
            self.assertEqual(first["terminal"][0]["status"], "DONE")
            self.assertEqual(first["terminal"][0]["status"], "DONE")

    def test_signal_file_is_not_reinterpreted_as_agent_checkin(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "states"
            directory.mkdir()
            signal = Path(root) / "dispatcher-check-required.json"
            marker = Path(root) / "marker"
            write_checkin(directory / "agent.json", state("DONE"))
            watch_once(directory, signal, marker, 10)
            signal.replace(directory / signal.name)
            result = inspect(directory, 10)
            self.assertEqual(result["outcome"], "ACTIONABLE")
            self.assertEqual(result["invalid_count"], 0)


if __name__ == "__main__":
    unittest.main()
