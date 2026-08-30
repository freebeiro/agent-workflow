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
