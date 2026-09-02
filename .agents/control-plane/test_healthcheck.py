import tempfile
import unittest
from pathlib import Path

from healthcheck import FILES, check


class HealthcheckTests(unittest.TestCase):
    def test_accepts_runtime_symlinks_and_physical_state(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "source"; runtime = root / "runtime"; state = root / "state"
            source.mkdir(); runtime.mkdir(); state.mkdir()
            for name in FILES:
                (source / name).write_text(name, encoding="utf-8")
                (runtime / name).symlink_to(source / name)
            self.assertEqual(check(source, runtime, state), [])

    def test_rejects_broken_or_divergent_runtime_links(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "source"; runtime = root / "runtime"; state = root / "state"
            source.mkdir(); runtime.mkdir(); state.mkdir()
            for name in FILES:
                (source / name).write_text(name, encoding="utf-8")
            (runtime / FILES[0]).symlink_to(source / FILES[0])
            (runtime / FILES[1]).symlink_to(root / "missing.py")
            (runtime / FILES[2]).write_text("copy", encoding="utf-8")
            (runtime / FILES[3]).symlink_to(source / FILES[3])
            errors = check(source, runtime, state)
            self.assertTrue(any("broken symlink" in error for error in errors))
            self.assertTrue(any("not a symlink" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
