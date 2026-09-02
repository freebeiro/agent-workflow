# Provider-Independent Agent Routing

This file defines routing by capability class, not by vendor or model name.
Provider-specific names belong only in `.agents/providers/`.

## Task categories

| Category | Default class | Effort | Use |
|---|---|---|---|
| `mechanical` | `cheap` | low/medium | Exact file edits, transcription, bounded checks |
| `bounded-analysis` | `mid` | medium | Analysis with fixed criteria and no new decisions |
| `decision` | `strong` | high | Product, architecture, scope, naming, or trade-offs |
| `cross-document` | `mid` | medium | Consistency work; use `strong` if contradictions require decisions |
| `high-risk` | `strong` | high | Security, irreversible, public, or migration changes |
| `verification` | `cheap` | low/medium | Tests, link checks, diff checks, evidence collection |

The `verification` default applies to mechanical evidence collection. An
initial or fresh milestone review is the only review dispatch forced to
`strong`/high; a focused recheck resumes that reviewer session rather than
routing a new model.

## Routing rules

1. The dispatcher is the sending tier. The orchestrator dispatches owner work
   to the architect and owns architect-session continuity; the architect
   dispatches executor/reviewer work. Each receiver may reject or escalate an
   invalid route. The dispatcher records `category`,
   `model_class`, `effort`, `reason`, and `confidence`.
2. Low-confidence routing defaults to `decision`, `strong`, `high`.
3. The architect validates the route after reading the task and may escalate.
4. No agent may downgrade unresolved ambiguity, a new decision, or high-risk
   work merely to reduce cost.
5. A role is defined by authority, not by model. A mid-tier model may perform
   an architect task only when the brief contains the decision, exact scope,
   constraints, and acceptance checks.
6. Unexpected results, failed verification, or a blocked executor escalate to
   the architect; repeated failure escalates to `strong`/`high` and may invoke
   the reviewer.
7. Every subagent ends a completed or blocked assignment with a final report
   beginning `DONE` or `BLOCKED`, containing changed files, verification/tests
   and results, blockers (or `none`), and the exact next action. After dispatch,
   the dispatcher consumes that report through an explicit native wait/join or
   event-wait; a completion notification alone does not restart a parent turn
   that has already ended. Polling/status checks are fallback diagnostics only.
   A final report ends substantive work for that assignment;
   a later fix requires a new dispatch. This notification supplements, and
   never replaces, the operational-handoff refresh required by `AGENTS.md`.
8. Every dispatched worker also writes a compact liveness check-in: `ACTIVE`
   on start/resume and `DONE`, `BLOCKED`, `WAITING_INPUT`, or
   `SESSION_UNAVAILABLE` before ending. The check-in is for the local watcher
   and must not be used as a substitute for the report, explicit wait/join, or
   handoff refresh. `IDLE` is not a valid workflow state.
9. After consuming a worker result, the Dispatcher must continue the state
   machine: refresh the handoff, resolve the next action through the Architect
   when judgment is needed, dispatch/resume the next approved step, and wait
   for its result. It may stop only at a legitimate terminal state, an
   explicit Owner decision gate, an unrecoverable failure, or unavailable
   replacement capacity. Worker `DONE` or session idle is not workflow `DONE`.
10. An Architect may spawn a bounded worker, but every spawned worker must be
   registered before execution with display identity, role, task, session,
   parent Architect, and Dispatcher. It must publish `ACTIVE` immediately.
   Unregistered work is not observable workflow work; escalate
   `SESSION_UNAVAILABLE` instead of silently creating an independent task.

## Capability classes

- `strong`: owns ambiguity, decisions, architecture, and high-risk judgment.
- `mid`: performs bounded reasoning and approved-plan application.
- `cheap`: performs mechanical work and low-risk verification.
- `reviewer`: an independent review role. Its initial or milestone audit uses a
  fresh `strong`/high session; focused remediation rechecks reuse that same
  session until a defined fresh-review trigger fires.

## Architect session continuity and reset policy

The dispatcher keeps one architect session for the current milestone and
resumes it for related work. A new session requires an explicit
`reset_reason`: `new_milestone`, `context_crowded`, `context_degraded`,
`blocked`, `independent_judgment`, `capability_change`, `provider_capacity`,
`session_unavailable`, or `owner_requested`.

At each meaningful boundary, the architect reports:

```yaml
estimated_remaining_turns: 5
context_quality: healthy # healthy | crowded | degraded
minimum_handoff: "decisions, current diff, and the next verification"
active_triggers: [session_unavailable]
decision_trigger: session_unavailable
```

The dispatcher, not the architect, applies the cost rule:

```text
continue_total = estimated_remaining_turns * current_session_turn_cost
restart_total = handoff_cost + required_read_cost
              + estimated_remaining_turns * fresh_session_turn_cost
```

All costs use the same provider-reported input-token-equivalent unit.

Trigger precedence is deterministic, in this order: explicit owner/manual
resets (`owner_requested`, `new_milestone`, `blocked`, `independent_judgment`),
then `session_unavailable`, `context_degraded`,
`capability_change`/`provider_capacity`, `context_crowded`
for utilisation >= 0.80, `CHECKPOINT_SOON` for utilisation >= 0.65, and
`cost_threshold` when utilisation is below 0.65 and
`continue_total > 1.2 * restart_total`; otherwise `CONTINUE`. The selected
highest-priority trigger supplies the decision reason. If telemetry is
unavailable, set all cost inputs and utilisation to `null` and use only the
quality/session gates; if those are also healthy, use `CONTINUE` and record
`telemetry_unavailable` as the decision trigger. Continuity overrides a
least-capable-model preference until a capability change is required.

Persist `active_triggers` and the derived `decision_trigger`; the validator
must reject a decision whose trigger is not present or not implied by the
observable state.

## Reviewer session continuity and review ledger

An integrated review is one **review cycle**. The architect creates
`tasks/reviews/<review-cycle-id>.md` from
`.agents/templates/REVIEW_LEDGER.template.md` before the initial dispatch and
stores its path plus the active reviewer session in the operational handoff.
The ledger is append-only history for the cycle; corrections add a dated entry
instead of rewriting a prior verdict.

The initial review at a new integrated changeset or explicit milestone is a
fresh independent session routed as `verification`, `strong`, high. Keep that
reviewer session for remediation rechecks so it retains the verified boundary,
stable finding IDs, prior evidence, and regression concerns. Findings return to
the same architect. The architect validates them and sends mechanical fixes to
one `mechanical`, `cheap`, low/medium executor at a time. The corrected tree
returns to the same reviewer; do not replace it merely because a fix round
began.

Each remediation-loop package contains only:

- the review-cycle and ledger paths, reviewer session identity, and stable open
  finding IDs copied verbatim;
- the original review boundary and acceptance criteria;
- the previous reviewed head, current head, and one fix-only diff package;
- changed paths, the executor report, exact tests and output, and any architect
  adjudication or owner decision that changed authority;
- named regression risks and out-of-scope observations already recorded in the
  ledger.

A focused recheck is read-only. It verdicts every open finding against current
evidence, inspects only the fix diff plus directly affected regression paths,
and records new breakage introduced by that diff. It does not reopen untouched
scope or inherit the architect's confidence. New issues wholly outside that
boundary enter the ledger for the next fresh milestone audit unless they are
critical evidence that the review boundary itself is invalid.

Start a fresh independent reviewer only when at least one trigger is recorded:

- `explicit_milestone`: an initial integrated gate or another owner/plan-named
  milestone audit;
- `architectural_scope_change`: architecture, acceptance criteria, review
  boundary, or affected subsystem changed after the initial review;
- `reviewer_context_cutoff`: provider-reported context utilisation is at least
  0.80, or, without telemetry, the reviewer reports `crowded` or `degraded`;
- `anchoring_risk`: three focused rechecks have occurred in the cycle; the
  reviewer saw fix authorship reasoning beyond the required package; a finding
  changes severity or disposition without new code or evidence; or architect
  and reviewer remain in substantive disagreement after one evidence-backed
  challenge;
- `session_unavailable` or `owner_requested`.

At reviewer utilisation of at least 0.65 but below 0.80, checkpoint the ledger
and handoff before another round. At 0.80, or when the boundary cannot be
established because telemetry and a reliable context-quality report are both
unavailable, stop using that session and dispatch a fresh `strong`/high reviewer
from the ledger and a new bounded package. When uncertain whether anchoring or
scope change is material, default to a fresh audit. Record the old and new
session identities, trigger, handoff package, and first fresh verdict.

The anti-anchoring safeguard is evidence, not amnesia: stable finding IDs and
prior observations remain in the ledger, but every recheck must cite current
file/test evidence and actively state what would disconfirm its prior finding.
A persistent reviewer is never automatically trusted, and a fresh audit remains
the escape hatch.

## Dispatch record

Every dispatch should be explainable with this shape:

```yaml
category: bounded-analysis
model_class: mid
effort: medium
reason: "Apply the approved plan to the named files"
confidence: high
fallback: "strong/high if the brief is incomplete or verification fails"
```

## Context-budget rules

Context is part of the cost of a dispatch. Send the smallest sufficient context
for the category:

- `mechanical`: exact brief, allowed files, acceptance checks, and relevant
  local tests. Do not send project history.
- `bounded-analysis`: brief, named sources, and only the code paths under
  analysis. Do not reread unrelated documents or transcripts.
- `decision`: the authoritative sources, relevant prior decisions, and the
  smallest evidence set needed to compare alternatives.
- `verification`: the review package/diff, acceptance criteria, and targeted
  tests. A reviewer must not scan the whole repository by default.
- `high-risk`: the changed surface, threat/decision sources, and focused
  adversarial tests. Expand scope only when evidence requires it.

Transcripts and living context are historical recovery material, not default
dispatch context. Include them only when the task explicitly requires causal
history or a handoff cannot be understood without them.

Every reviewer brief must name its review-cycle and ledger paths, reviewer
session identity, review boundary, changed paths, base and head revisions (or
an equivalent diff), and the exact verdict schema. Use one fresh reviewer for
the initial integrated gate, then the same reviewer for focused remediation
rechecks until a recorded fresh-review trigger fires.

Provider mappings are recommendations, not authority rules:

- Claude: `.agents/providers/claude.md`
- OpenAI/Codex: `.agents/providers/openai.md`
- Unknown or future provider: `.agents/providers/generic.md`
