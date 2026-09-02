#!/usr/bin/env python3
"""Private read-only browser dashboard for project control planes."""
from __future__ import annotations

import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from healthcheck import check
from watcher import inspect


HTML = """<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Control Plane</title><style>
body{font:15px system-ui;background:#101218;color:#e9edf5;margin:0;padding:20px}h1{font-size:24px}
main{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}.card{background:#1a1e28;border:1px solid #303746;border-radius:12px;padding:16px}.ok{color:#62d895}.bad{color:#ff7b87}.workers{display:grid;gap:8px}.worker{background:#242a36;border-radius:8px;padding:10px}.muted{color:#aab2c2;font-size:13px}.status{font-weight:700}
</style><h1>Control Plane</h1><main id=app>Loading…</main><script>
async function refresh(){const r=await fetch('/api/state',{cache:'no-store'});const d=await r.json();document.querySelector('#app').innerHTML=d.projects.map(p=>`<section class=card><h2>${esc(p.project_id)}</h2><p class=${p.health.ok?'ok':'bad'}>${p.health.ok?'HEALTHY':'UNHEALTHY'}</p><div class=workers>${p.workers.map(w=>`<article class=worker><span class=status>${esc(w.status)}</span> ${esc(w.display_name)} <span class=muted>${esc(w.role)} · ${esc(w.task_id)} · ${Math.round(w.age_seconds)}s</span><br><span class=muted>${esc(w.next_action||'')}</span></article>`).join('')||'<span class=muted>No workers</span>'}</div></section>`).join('')||'<p>No projects configured</p>'}function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}refresh();setInterval(refresh,1000);
</script>"""


def load_projects(path: Path) -> list[dict[str, str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    projects = value.get("projects") if isinstance(value, dict) else None
    if not isinstance(projects, list):
        raise ValueError("config must contain a projects list")
    return [p for p in projects if isinstance(p, dict) and all(isinstance(p.get(k), str) and p[k] for k in ("project_id", "state", "runtime", "source"))]


def snapshot(projects: list[dict[str, str]]) -> dict[str, Any]:
    result = []
    for project in projects:
        state = Path(project["state"]); source = Path(project["source"]); runtime = Path(project["runtime"])
        view = None
        try:
            view = inspect(state, 10, state / "registry.json")
            errors = check(source, runtime, state)
            health = {"ok": not errors, "errors": errors}
            workers = view["states"]
        except (OSError, ValueError, json.JSONDecodeError) as error:
            health = {"ok": False, "errors": [str(error)]}; workers = []
        result.append({"project_id": project["project_id"], "health": health, "workers": workers, "outcome": view["outcome"] if view and view.get("outcome") else "UNAVAILABLE"})
    return {"projects": result}


def create_server(host: str, port: int, config: Path, token: str | None):
    class Handler(BaseHTTPRequestHandler):
        def authorized(self) -> bool:
            return not token or secrets.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}")
        def do_GET(self):
            if not self.authorized(): self.send_error(401); return
            if self.path == "/": body, content = HTML.encode(), "text/html; charset=utf-8"
            elif self.path == "/api/state": body, content = json.dumps(snapshot(load_projects(config))).encode(), "application/json"
            else: self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type", content); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
        def log_message(self, *_): pass
    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--config", type=Path, required=True); parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8765); parser.add_argument("--token", default=None)
    args = parser.parse_args(); server = create_server(args.host, args.port, args.config, args.token)
    print(f"Dashboard listening on http://{args.host}:{server.server_port}", flush=True); server.serve_forever(); return 0


if __name__ == "__main__": raise SystemExit(main())
