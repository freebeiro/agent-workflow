# Review ledger — <review-cycle-id>

Append at every review, fix-dispatch, fix-completion, recheck, replacement, or
gate transition. Do not rewrite prior entries; append a correction that cites
the superseded entry.

## Cycle identity

- milestone:
- architect session:
- review boundary:
- acceptance criteria:
- base / initially reviewed head:
- changed paths:
- risk classification:
- initial reviewer session:
- provider / effective model / capability class / effort:
- initial dispatch reason and confidence:
- initial review package:

## Reviewer context state

- telemetry available: yes | no
- context utilisation: <0.00-1.00 | unavailable>
- context quality: healthy | crowded | degraded | unavailable
- focused recheck count:
- latest cutoff or anti-anchoring assessment:
- fresh-review trigger: none | explicit_milestone |
  architectural_scope_change | reviewer_context_cutoff | anchoring_risk |
  session_unavailable | owner_requested

## Findings

Give every finding a stable ID. Preserve its original wording and severity;
later changes are appended as verdicts or corrections with current evidence.

### <FINDING-ID> — <title>

- original severity:
- original statement:
- file / line evidence:
- acceptance criterion or authority:
- disconfirming evidence that would overturn it:
- current status: open | addressed | not-addressed | superseded | parked

## Remediation rounds

### Round <N> — <timestamp>

- open finding IDs sent verbatim:
- previous reviewed head / current head:
- fix-only diff package:
- changed paths:
- executor session and effective provider/model/class/effort:
- executor report:
- exact verification command and output:
- architect adjudication or owner decision, if authority changed:
- named regression risks:
- reviewer session reused:
- focused recheck evidence and per-finding verdicts:
- new breakage in the fix diff:
- out-of-scope observations for the next fresh milestone audit:
- reviewer context state after recheck:
- next action:

## Reviewer replacements

### Replacement <N> — <timestamp>

- prior reviewer session:
- trigger and evidence:
- ledger checkpoint / bounded handoff package:
- new fresh reviewer session:
- provider / effective model / capability class / effort:
- first fresh verdict:

## Gate state

- latest verdict:
- open finding IDs:
- authorization gates:
- exact next action:
- operational handoff refreshed and inspected at:
