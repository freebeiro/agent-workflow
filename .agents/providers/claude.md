# Claude Provider Mapping

Map the provider-independent classes as follows:

| Class | Recommended mapping |
|---|---|
| `strong` | Opus, usually medium effort; high for decisions/high risk |
| `mid` | Sonnet, medium effort |
| `cheap` | Sonnet low/medium or Haiku where available |
| `reviewer` | Fresh Opus/high for initial or milestone review; resume that session for focused rechecks |

Model names and availability are provider configuration, not repository
authority. If a named model is unavailable, use the nearest capability class.

## Claude Code topology: Dispatcher, Architect, Executor

This section is Claude-specific. It describes how the roles defined in
`AGENTS.md` and routed by `.agents/ROUTING.md` are realised in the Claude Code
CLI harness. It adds no capability classes and changes no mapping above.

1. The top-level Claude Code session is the Dispatcher and nothing else. It
   does not read specs, plan, review diffs, or write or run code. It holds
   routing state, task status, and handoff pointers only, and keeps Owner
   exchanges short.
2. The Dispatcher spawns the Architect as a subagent with the `Agent` tool,
   routed by the category table in `.agents/ROUTING.md`: `strong` (Opus) for
   `decision` and `high-risk` work, `mid` (Sonnet) for `bounded-analysis`.
3. The Architect dispatches Executor and reviewer work itself, by calling the
   `Agent` tool from within its own subagent session. This satisfies routing
   rule 1 directly; the Claude Code host supports recursive delegation, so the
   Dispatcher must not relay Executor briefs mechanically.
4. An Executor is spawned at the least capable sufficient class: `mid`
   (Sonnet) for `mechanical` and `bounded-analysis`, `cheap` (Haiku where
   available) for trivial `mechanical` and `verification` work. Routing rule 11
   applies: raising an Executor to `strong` requires a stated reason.
5. Liveness and wait/join are native here. A background subagent's completion
   notifies its invoking session, so a Claude-only chain may skip
   `.agents/control-plane/checkin.py` and the file watcher. This exemption is
   Claude-only. The check-in and watcher system is not deprecated: providers
   without native cross-session wait/join, including Codex, still require it as
   specified in `.agents/ROUTING.md` rule 8.
6. When an Architect needs Owner input, it ends its turn with the question, or
   surfaces the question in its final report. The Dispatcher relays it in
   minimal form and routes the Owner's answer back to the same Architect
   subagent as a session-continuing message. It does not spawn a fresh
   Architect for the answer; this is the architect-session-continuity rule
   applied through the harness's own continuation mechanism.
7. Class selection stays with the category table: `mechanical` to `cheap`,
   `bounded-analysis` to `mid`, `decision` and `high-risk` to `strong`,
   `verification` to `cheap`. Availability of a strong model is not a reason to
   use it. Spawning every subagent at `strong` violates routing rule 11.
