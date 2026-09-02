# Shared Agent Workflow

Reusable, provider-neutral workflow infrastructure for projects using a
Dispatcher, Architect/Reviewer, and Executor topology.

## Install in another project

From a cloned copy:

```bash
./install.sh --project-id my-project /path/to/project
```

From GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/freebeiro/agent-workflow/main/install.sh | bash -s -- --project-id my-project /path/to/project
```

Add `--project-id my-project` to the GitHub command. On macOS, installation
also activates an isolated `launchd` watcher under `~/.codex/agent-workflow/`.
Use `--no-watch` to install files without activating it.

The installer copies the shared `.agents/` framework. If the target has no
`AGENTS.md`, it installs the shared contract. If one already exists, it leaves
it untouched and reports that it needs a project-specific merge. Use
`--replace-agents` only after reviewing the backup and intended project
adapter.

On macOS, each project keeps its own state under
`~/.codex/agent-workflow/<project-id>/state/`, while control-plane programs
are symlinks to a versioned shared runtime under
`~/.codex/agent-workflow/runtime/<ref>/`. This allows multiple projects to
share one implementation without sharing check-ins or histories. Verify an
installation with `healthcheck.py` using the project source, runtime, and
state paths.

The installer never changes product documents, `CONTEXT.md`,
`PROJECT_PROFILE.md`, source code, or existing operational state.

## What is shared and what is local

Shared: skills, routing policy, provider adapters, templates, and handoff
validation tooling.

Optional browser dashboard: create a JSON configuration with each project's
state, runtime, and source paths, then run the installed read-only dashboard.
It refreshes every second:

```json
{"projects":[{"project_id":"my-project","state":"/home/me/.codex/agent-workflow/my-project/state","runtime":"/home/me/.codex/agent-workflow/my-project/control-plane","source":"/path/to/my-project/.agents/control-plane"}]}
```

```bash
python3 ~/.codex/agent-workflow/my-project/control-plane/dashboard.py \
  --config ~/.codex/agent-workflow/dashboard-projects.json \
  --token "use-a-long-local-secret"
```

Open `http://127.0.0.1:8765` locally. For mobile access outside home, bind
explicitly to the private Tailscale interface with `--host 100.x.y.z`; do not
bind publicly without a private network and token.

Local: project profile, product context, specifications, source code, and
project operational state.

Projects should pin a release or commit when reproducibility matters. The
workflow is intentionally provider-neutral; provider mappings remain adapters.

## Low-cost liveness check-ins

Agents can write one compact JSON check-in per task:

```bash
python3 .agents/control-plane/checkin.py .agents/state/agent-1.json \
  --agent-id agent-1 --task-id task-1 --status ACTIVE \
  --timestamp 2026-08-31T12:00:00+00:00 --next-action continue \
  --eta 2m --report-ref tasks/reports/task-1.md
```

When the installer activates the macOS watcher, use its external state
directory instead of a repository-local one:

```bash
STATE_DIR="$HOME/.codex/agent-workflow/my-project/state"
python3 .agents/control-plane/checkin.py "$STATE_DIR/agent-1.json" \
  --agent-id agent-1 --task-id task-1 --status ACTIVE \
  --timestamp 2026-08-31T12:00:00+00:00 --next-action continue \
  --eta 2m --report-ref tasks/reports/task-1.md
```

The shared `AGENTS.md` contract requires this check-in at assignment start,
meaningful boundaries, and assignment end. The Dispatcher puts the same
instruction in worker briefs; routine `ACTIVE` updates remain silent.

A local watcher can run every 2 minutes without loading agent context:

```bash
python3 .agents/control-plane/watcher.py .agents/state --json
```

It returns `QUIET` while work is active, `ACTIONABLE` when all observed
agents are terminal, `TIMEOUT` for stale active work, and `INVALID` for bad
state. The watcher does not wake or call an external service. Codex heartbeat
automations must remain the host-specific fallback; if the host cannot perform
conditional wakes, configure a silent heartbeat and accept that the host may
wake the Dispatcher periodically.

For event-driven CLI operation, use the supervisor. It polls locally as often
as desired and resumes the named Dispatcher session only once per new signal:

```bash
python3 .agents/control-plane/dispatcher_wake.py .agents/state \
  --session-id DISPATCHER_SESSION_ID --interval-seconds 2 --dry-run
```

Remove `--dry-run` only after confirming the session ID and Codex CLI login.
The command uses the local Codex CLI session; it does not call an external API.
The Desktop UI may not reflect CLI-resumed turns reliably, so this is intended
for a headless/CLI Dispatcher with the UI used for observation.

For the UI-compatible, non-invasive mode, run `codex_watch.py` instead. It
polls every two seconds by default, consumes no model tokens, never calls the
Dispatcher, and atomically writes one durable signal per new actionable state:

```bash
python3 .agents/control-plane/codex_watch.py .agents/state \
  --signal .agents/state/dispatcher-check-required.json
```

The existing heartbeat can read that signal on its next run. This provides
early local detection without changing the automation schedule. Remove the
signal only after the Dispatcher has recorded the corresponding handoff
boundary; the watcher will emit it again only after a new state change.
