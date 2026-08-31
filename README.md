# Shared Agent Workflow

Reusable, provider-neutral workflow infrastructure for projects using a
Dispatcher, Architect/Reviewer, and Executor topology.

## Install in another project

From a cloned copy:

```bash
./install.sh /path/to/project
```

From GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/freebeiro/agent-workflow/main/install.sh | bash -s -- /path/to/project
```

The installer copies the shared `.agents/` framework. If the target has no
`AGENTS.md`, it installs the shared contract. If one already exists, it leaves
it untouched and reports that it needs a project-specific merge. Use
`--replace-agents` only after reviewing the backup and intended project
adapter.

The installer never changes product documents, `CONTEXT.md`,
`PROJECT_PROFILE.md`, source code, or existing operational state.

## What is shared and what is local

Shared: skills, routing policy, provider adapters, templates, and handoff
validation tooling.

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
