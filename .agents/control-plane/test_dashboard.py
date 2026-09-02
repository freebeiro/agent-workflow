import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from dashboard import create_server, snapshot


class DashboardTests(unittest.TestCase):
    def test_snapshot_groups_workers_and_reports_health(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); state = root / "state"; state.mkdir()
            (state / "registry.json").write_text("{}\n", encoding="utf-8")
            projects = [{"project_id": "demo", "state": str(state),
                         "runtime": str(root / "runtime"), "source": str(root / "source")}]
            result = snapshot(projects)
            self.assertEqual(result["projects"][0]["project_id"], "demo")
            self.assertIn("workers", result["projects"][0])
            self.assertIn("health", result["projects"][0])

    def test_http_dashboard_refreshes_and_requires_token(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); state = root / "state"; state.mkdir()
            config = root / "projects.json"
            config.write_text(json.dumps({"projects": [{"project_id": "demo", "state": str(state), "runtime": str(root / "runtime"), "source": str(root / "source")}] }), encoding="utf-8")
            server = create_server("127.0.0.1", 0, config, "secret")
            try:
                server_thread = __import__("threading").Thread(target=server.serve_forever, daemon=True); server_thread.start()
                url = f"http://127.0.0.1:{server.server_port}/api/state"
                with self.assertRaises(Exception): urlopen(url)
                request = Request(url, headers={"Authorization": "Bearer secret"})
                response = urlopen(request)
                self.assertEqual(response.status, 200)
                self.assertIn(b"projects", response.read())
                page_request = Request(f"http://127.0.0.1:{server.server_port}/", headers={"Authorization": "Bearer secret"})
                page = urlopen(page_request).read().decode()
                self.assertIn("setInterval", page)
            finally:
                server.shutdown(); server.server_close()


if __name__ == "__main__":
    unittest.main()
