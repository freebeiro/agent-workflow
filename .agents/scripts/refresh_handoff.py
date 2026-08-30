#!/usr/bin/env python3
"""Create a deterministic, provider-neutral local handoff packet."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import argparse
import base64
import binascii
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from urllib.parse import parse_qsl, urlsplit


class HandoffError(ValueError):
    """Raised when handoff inputs cannot be trusted."""


REQUIRED_STATE_KEYS = frozenset(
    {
        "schema_version",
        "updated_at",
        "objective",
        "stage",
        "active_task",
        "task_brief",
        "first_incomplete_action",
        "latest_result",
        "expected_verification",
        "authorization_gates",
        "prohibited_actions",
        "incomplete_work_origin",
        "next_action",
        "orchestration",
        "review",
    }
)

_STRING_KEYS = frozenset(
    {
        "objective",
        "stage",
        "active_task",
        "task_brief",
        "first_incomplete_action",
        "latest_result",
        "incomplete_work_origin",
        "next_action",
    }
)
_LIST_KEYS = frozenset(
    {"expected_verification", "authorization_gates", "prohibited_actions"}
)
_ORCHESTRATION_KEYS = frozenset(
    {
        "milestone",
        "architect_session",
        "model_class",
        "effort",
        "estimated_remaining_turns",
        "context_quality",
        "context_utilization",
        "telemetry_available",
        "current_session_turn_cost",
        "handoff_cost",
        "required_read_cost",
        "fresh_session_turn_cost",
        "continuity_decision",
        "decision_reason",
        "reset_reason",
        "minimum_handoff",
        "active_triggers",
        "decision_trigger",
    }
)
_ORCHESTRATION_ENUMS = {
    "context_quality": frozenset({"healthy", "crowded", "degraded"}),
    "continuity_decision": frozenset({"CONTINUE", "CHECKPOINT_SOON", "RESET"}),
    "reset_reason": frozenset({
        "none", "new_milestone", "context_crowded", "context_degraded", "blocked",
        "independent_judgment", "owner_requested", "capability_change",
        "provider_capacity", "session_unavailable", "cost_threshold",
    }),
    "decision_trigger": frozenset({
        "none", "telemetry_unavailable", "utilization_checkpoint", "context_crowded",
        "context_degraded", "session_unavailable", "capability_change", "provider_capacity",
        "new_milestone", "blocked", "independent_judgment", "owner_requested", "cost_threshold",
    }),
}
_ACTIVE_TRIGGERS = frozenset(set(_ORCHESTRATION_ENUMS["decision_trigger"]) - {"none", "telemetry_unavailable", "utilization_checkpoint"})
_REVIEW_KEYS = frozenset(
    {
        "cycle_id",
        "status",
        "review_kind",
        "ledger_path",
        "reviewer_session",
        "context_quality",
        "context_utilization",
        "telemetry_available",
        "focused_recheck_count",
        "fresh_review_trigger",
        "last_reviewed_head",
        "open_findings",
    }
)
_REVIEW_ENUMS = {
    "status": frozenset({"inactive", "initial_review", "remediation", "recheck", "passed", "blocked", "replaced"}),
    "review_kind": frozenset({"none", "initial", "fresh_milestone", "focused_recheck"}),
    "context_quality": frozenset({"healthy", "crowded", "degraded", "unavailable"}),
    "fresh_review_trigger": frozenset({
        "none", "explicit_milestone", "architectural_scope_change",
        "reviewer_context_cutoff", "anchoring_risk", "session_unavailable",
        "owner_requested",
    }),
}
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)(?:^|[\s,;])(?:authorization|bearer|token|api[_-]?key|password|secret|credential)"
    r"\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_BARE_BEARER = re.compile(r"(?i)\bbearer\s+(?=\S*[0-9._-])\S+")
_GITHUB_PAT = re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b")
_JWT_SHAPE = re.compile(
    r"\b(?P<header>[A-Za-z0-9_-]{4,})\.(?P<payload>[A-Za-z0-9_-]{4,})\.(?P<signature>[A-Za-z0-9_-]{4,})\b"
)
_PRIVATE_KEY_MARKER = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")


def _looks_like_jwt_header(segment: str) -> bool:
    padded = segment + "=" * (-len(segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded)
    except (ValueError, binascii.Error):
        return False
    return decoded.lstrip().startswith(b'{"')


def _has_jwt_shape(value: str) -> bool:
    return any(_looks_like_jwt_header(m.group("header")) for m in _JWT_SHAPE.finditer(value))


def _has_durable_credential(value: str) -> bool:
    return bool(
        _CREDENTIAL_ASSIGNMENT.search(value)
        or _BARE_BEARER.search(value)
        or _GITHUB_PAT.search(value)
        or _has_jwt_shape(value)
        or _PRIVATE_KEY_MARKER.search(value)
    )
MAX_DIFF_STAT_BYTES = 8192
MAX_STATUS_BYTES = 16_384
MAX_REMOTE_BYTES = 16_384
MAX_RENDERED_UTF8_BYTES = 32_768
_REMOTE_CREDENTIAL_QUERY_KEYS = frozenset(
    {"access_token", "api_key", "apikey", "auth", "authorization", "credential", "password", "secret", "token"}
)
TEMPLATE_TOKENS = (
    "HANDOFF_TIMESTAMP",
    "OBJECTIVE",
    "STAGE",
    "ACTIVE_TASK",
    "TASK_BRIEF",
    "FIRST_INCOMPLETE_ACTION",
    "LATEST_RESULT",
    "EXPECTED_VERIFICATION",
    "AUTHORIZATION_GATES",
    "PROHIBITED_ACTIONS",
    "INCOMPLETE_WORK_ORIGIN",
    "NEXT_ACTION",
    "ORCHESTRATION",
    "REVIEW",
    "REPOSITORY_ROOT",
    "WORKTREE",
    "BRANCH",
    "HEAD",
    "CLEAN",
    "STATUS_LINES",
    "STAGED_FILES",
    "UNSTAGED_FILES",
    "UNTRACKED_FILES",
    "STAGED_DIFF_STAT",
    "UNSTAGED_DIFF_STAT",
    "REMOTES",
    "BOOTSTRAP_PROMPT",
)
_TOKEN_PATTERN = re.compile(r"\{\{([A-Z_]+)\}\}")


@dataclass(frozen=True)
class GitFacts:
    repository_root: Path
    worktree: Path
    branch: str
    head: str
    status_lines: tuple[str, ...]
    staged_files: tuple[str, ...]
    unstaged_files: tuple[str, ...]
    untracked_files: tuple[str, ...]
    staged_diff_stat: str
    unstaged_diff_stat: str
    remotes: tuple[str, ...]

    @property
    def clean(self) -> bool:
        return not (self.staged_files or self.unstaged_files or self.untracked_files)


def _reject() -> None:
    raise HandoffError("Invalid handoff state.")


def _pairs_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _reject()
        result[key] = value
    return result


def _reject_nonfinite(_: str) -> object:
    _reject()


def _valid_text(value: object) -> bool:
    return type(value) is str and bool(value.strip()) and not _has_durable_credential(value)


def _validate_task_brief(value: str) -> None:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "\\" in value
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        _reject()


def _validate_state(state: object) -> dict[str, object]:
    if type(state) is not dict or set(state) != REQUIRED_STATE_KEYS:
        _reject()
    if type(state["schema_version"]) is not int or state["schema_version"] != 3:
        _reject()
    updated_at = state["updated_at"]
    if not _valid_text(updated_at):
        _reject()
    try:
        timestamp = datetime.fromisoformat(updated_at)
    except (TypeError, ValueError):
        _reject()
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        _reject()
    for key in _STRING_KEYS:
        value = state[key]
        if not _valid_text(value):
            _reject()
    _validate_task_brief(state["task_brief"])
    for key in _LIST_KEYS:
        values = state[key]
        if type(values) is not list or any(not _valid_text(value) for value in values):
            _reject()
    orchestration = state["orchestration"]
    if type(orchestration) is not dict or set(orchestration) != _ORCHESTRATION_KEYS:
        _reject()
    for key in ("milestone", "architect_session", "model_class", "effort", "decision_reason", "minimum_handoff"):
        if not _valid_text(orchestration[key]):
            _reject()
    for key, allowed in _ORCHESTRATION_ENUMS.items():
        if orchestration[key] not in allowed:
            _reject()
    active = orchestration["active_triggers"]
    if type(active) is not list or len(active) != len(set(active)) or any(value not in _ACTIVE_TRIGGERS for value in active):
        _reject()
    for key in ("estimated_remaining_turns",):
        if type(orchestration[key]) is not int or orchestration[key] < 0:
            _reject()
    utilization = orchestration["context_utilization"]
    if utilization is not None and (type(utilization) not in (int, float) or not 0 <= utilization <= 1):
        _reject()
    for key in ("current_session_turn_cost", "handoff_cost", "required_read_cost", "fresh_session_turn_cost"):
        if orchestration[key] is not None and (type(orchestration[key]) not in (int, float) or orchestration[key] < 0):
            _reject()
    if type(orchestration["telemetry_available"]) is not bool:
        _reject()
    if not orchestration["telemetry_available"] and (utilization is not None or any(orchestration[key] is not None for key in ("current_session_turn_cost", "handoff_cost", "required_read_cost", "fresh_session_turn_cost"))):
        _reject()
    if orchestration["telemetry_available"] and (utilization is None or any(orchestration[key] is None for key in ("current_session_turn_cost", "handoff_cost", "required_read_cost", "fresh_session_turn_cost"))):
        _reject()
    decision = orchestration["continuity_decision"]
    quality = orchestration["context_quality"]
    session_missing = orchestration["architect_session"] == "not-attached"
    if orchestration["telemetry_available"]:
        continue_total = orchestration["estimated_remaining_turns"] * orchestration["current_session_turn_cost"]
        restart_total = orchestration["handoff_cost"] + orchestration["required_read_cost"] + orchestration["estimated_remaining_turns"] * orchestration["fresh_session_turn_cost"]
        cost_fires = continue_total > 1.2 * restart_total
    else:
        cost_fires = False
    candidates = set(active)
    if session_missing:
        candidates.add("session_unavailable")
    if quality == "degraded":
        candidates.add("context_degraded")
    if utilization is not None and utilization >= 0.80:
        candidates.add("context_crowded")
    checkpoint = utilization is not None and 0.65 <= utilization < 0.80
    if cost_fires and utilization is not None and utilization < 0.65:
        candidates.add("cost_threshold")
    if not orchestration["telemetry_available"] and quality == "crowded":
        candidates.add("context_crowded")
    if "session_unavailable" in active and not session_missing:
        _reject()
    if "context_degraded" in active and quality != "degraded":
        _reject()
    if "context_crowded" in active and not ((utilization is not None and utilization >= 0.80) or (not orchestration["telemetry_available"] and quality == "crowded")):
        _reject()
    if "cost_threshold" in active and not (cost_fires and utilization is not None and utilization < 0.65):
        _reject()
    priority = ("owner_requested", "new_milestone", "blocked", "independent_judgment",
                "session_unavailable", "context_degraded", "capability_change",
                "provider_capacity", "context_crowded", "cost_threshold")
    chosen = next((item for item in priority if item in candidates), None)
    expected_trigger = chosen or ("utilization_checkpoint" if checkpoint else ("telemetry_unavailable" if not orchestration["telemetry_available"] else "none"))
    expected_decision = "RESET" if chosen else ("CHECKPOINT_SOON" if checkpoint else "CONTINUE")
    expected_reason = chosen or "none"
    if orchestration["decision_trigger"] != expected_trigger or decision != expected_decision or orchestration["reset_reason"] != expected_reason:
        _reject()
    expected_message = {
        "none": "No reset trigger; continue the current architect session.",
        "telemetry_unavailable": "Telemetry unavailable; continue conservatively.",
        "utilization_checkpoint": "Context utilisation reached the checkpoint threshold.",
        "session_unavailable": "The current architect session is unavailable.",
        "context_degraded": "Context quality is degraded.",
        "context_crowded": "Context utilisation or quality is crowded.",
        "capability_change": "A capability change requires a new session.",
        "provider_capacity": "Provider capacity requires a new session.",
        "owner_requested": "The owner requested a new session.",
        "new_milestone": "A new milestone requires a new session.",
        "blocked": "The current architect is blocked.",
        "independent_judgment": "Independent judgment requires a fresh session.",
        "cost_threshold": "Continuing costs more than restarting from the compact handoff.",
    }[expected_trigger]
    if orchestration["decision_reason"] != expected_message:
        _reject()
    if orchestration["decision_trigger"] not in {"none", "telemetry_unavailable", "utilization_checkpoint"} and orchestration["decision_trigger"] not in active:
        _reject()
    review = state["review"]
    if type(review) is not dict or set(review) != _REVIEW_KEYS:
        _reject()
    for key in ("cycle_id", "ledger_path", "reviewer_session", "last_reviewed_head"):
        if not _valid_text(review[key]):
            _reject()
    for key, allowed in _REVIEW_ENUMS.items():
        if review[key] not in allowed:
            _reject()
    if type(review["focused_recheck_count"]) is not int or review["focused_recheck_count"] < 0:
        _reject()
    if type(review["telemetry_available"]) is not bool:
        _reject()
    review_utilization = review["context_utilization"]
    if review_utilization is not None and (
        type(review_utilization) not in (int, float)
        or not 0 <= review_utilization <= 1
    ):
        _reject()
    if not review["telemetry_available"] and review_utilization is not None:
        _reject()
    if review["telemetry_available"] and review_utilization is None:
        _reject()
    findings = review["open_findings"]
    if type(findings) is not list or len(findings) != len(set(findings)) or any(not _valid_text(value) for value in findings):
        _reject()
    if review["status"] == "inactive":
        if (
            review["review_kind"] != "none"
            or review["reviewer_session"] != "not-attached"
            or review["focused_recheck_count"] != 0
            or findings
        ):
            _reject()
    else:
        ledger = PurePosixPath(review["ledger_path"])
        if (
            ledger.is_absolute()
            or ledger.suffix != ".md"
            or ledger.parts[:2] != ("tasks", "reviews")
            or any(part in {"", ".", ".."} for part in ledger.parts)
            or review["reviewer_session"] == "not-attached"
            or review["review_kind"] == "none"
        ):
            _reject()
    if review_utilization is not None and review_utilization >= 0.80 and review["fresh_review_trigger"] != "reviewer_context_cutoff":
        _reject()
    if review["focused_recheck_count"] >= 3 and review["fresh_review_trigger"] != "anchoring_risk":
        _reject()
    return state


def load_state(path: Path) -> dict[str, object]:
    """Load and strictly validate the semantic state JSON without echoing it."""
    try:
        raw = path.read_text(encoding="utf-8")
        state = json.loads(
            raw,
            object_pairs_hook=_pairs_object,
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError, HandoffError):
        _reject()
    return _validate_state(state)


def _run_git(repo: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ("git", "-C", str(repo), *args),
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        raise HandoffError("Unable to collect Git facts.") from None


def _decode_git(data: bytes) -> str:
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise HandoffError("Git facts are not valid UTF-8.") from None


def _bounded_stat(repo: Path, *args: str) -> str:
    output = _run_git(repo, *args)
    if len(output) > MAX_DIFF_STAT_BYTES:
        output = output[:MAX_DIFF_STAT_BYTES]
        while output:
            try:
                return _decode_git(output).rstrip("\n")
            except HandoffError:
                output = output[:-1]
    return _decode_git(output).rstrip("\n")


_SCP_LIKE_REMOTE = re.compile(r"^(?P<userinfo>[^/@\s]+)@(?P<host>[^/@:\s]+):(?!//)(?P<path>.+)$")


def _remote_has_credential(url: str) -> bool:
    if "://" not in url:
        match = _SCP_LIKE_REMOTE.match(url)
        if match is None:
            return False
        return ":" in match.group("userinfo")
    try:
        parsed = urlsplit(url)
    except ValueError:
        return True
    if parsed.password is not None:
        return True
    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    if parsed.username is not None:
        return True
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = key.lower().replace("-", "_")
        if (
            normalized in _REMOTE_CREDENTIAL_QUERY_KEYS
            or normalized.endswith("_token")
            or normalized.endswith("_key")
        ):
            return True
    return False


def _collect_remotes(repo: Path) -> tuple[str, ...]:
    raw_remotes = _run_git(repo, "remote", "-v")
    if len(raw_remotes) > MAX_REMOTE_BYTES:
        raise HandoffError("Git remote input exceeds handoff bounds.")
    remotes: list[str] = []
    for raw_line in _decode_git(raw_remotes).splitlines():
        fields = raw_line.split()
        if not fields:
            continue
        if len(fields) != 3:
            raise HandoffError("Unexpected Git remote.")
        name, url, direction = fields
        if _remote_has_credential(url):
            raise HandoffError("Credential-bearing Git remote.")
        remotes.append(f"{name} {url} {direction}")
    return tuple(sorted(remotes))


def _porcelain_paths(data: bytes) -> tuple[
    tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]
]:
    staged: set[str] = set()
    unstaged: set[str] = set()
    untracked: set[str] = set()
    lines: list[str] = []
    fields = data.split(b"\0")
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if not record:
            continue
        text = _decode_git(record)
        if len(text) < 4:
            raise HandoffError("Unexpected Git status.")
        code, path = text[:2], text[3:]
        if not path:
            raise HandoffError("Unexpected Git status.")
        destination = PurePosixPath(path).as_posix()
        paths = [destination]
        display_path = destination
        if "R" in code or "C" in code:
            if index >= len(fields) or not fields[index]:
                raise HandoffError("Unexpected Git rename status.")
            source = PurePosixPath(_decode_git(fields[index])).as_posix()
            paths.append(source)
            display_path = f"{source} -> {destination}"
            index += 1
        normalized = tuple(sorted(paths))
        lines.append(f"{code} {display_path}")
        if code == "??":
            untracked.update(normalized)
            continue
        if code[0] not in {" ", "?"}:
            staged.update(normalized)
        if code[1] not in {" ", "?"}:
            unstaged.update(normalized)
    return tuple(sorted(lines)), tuple(sorted(staged)), tuple(sorted(unstaged)), tuple(sorted(untracked))


def collect_git_facts(repo: Path) -> GitFacts:
    """Observe the current repository without changing index, refs, or configuration."""
    requested = repo.resolve(strict=False)
    root_text = _decode_git(_run_git(requested, "rev-parse", "--show-toplevel")).strip()
    root = Path(root_text).resolve(strict=True)
    worktree = requested
    status = _run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if len(status) > MAX_STATUS_BYTES:
        raise HandoffError("Git status input exceeds handoff bounds.")
    status_lines, staged, unstaged, untracked = _porcelain_paths(status)
    branch_name = _decode_git(_run_git(root, "rev-parse", "--abbrev-ref", "HEAD")).strip()
    branch = "HEAD detached" if branch_name == "HEAD" else branch_name
    remotes = _collect_remotes(root)
    return GitFacts(
        repository_root=root,
        worktree=worktree,
        branch=branch,
        head=_decode_git(_run_git(root, "rev-parse", "HEAD")).strip(),
        status_lines=status_lines,
        staged_files=staged,
        unstaged_files=unstaged,
        untracked_files=untracked,
        staged_diff_stat=_bounded_stat(root, "diff", "--cached", "--stat", "--no-ext-diff"),
        unstaged_diff_stat=_bounded_stat(root, "diff", "--stat", "--no-ext-diff"),
        remotes=remotes,
    )


def _list_block(values: object) -> str:
    if type(values) is not list:
        _reject()
    return "\n".join(f"- {value}" for value in values) if values else "- none"


def _code_block(values: tuple[str, ...] | str) -> str:
    if type(values) is tuple:
        text = "\n".join(values) if values else "none"
    else:
        text = values or "none"
    return f"```text\n{text}\n```"


def _bootstrap_prompt() -> str:
    return (
        "Continue in the same local workspace. Read AGENTS.md, this handoff, the "
        "living context, approved design and plan, active plan ledger, and task "
        "brief completely before acting. Verify Git and toolchain state, preserve "
        "dirty work, then resume the first incomplete action. Apply project-local "
        "skills, review gates, context checkpoints, and authority limits. Do not "
        "repeat completed work, publish, merge, or deploy without explicit "
        "authorization."
    )


def _orchestration_block(value: object) -> str:
    if type(value) is not dict:
        _reject()
    return "```yaml\n" + json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def _review_block(value: object) -> str:
    if type(value) is not dict:
        _reject()
    return "```yaml\n" + json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def render_handoff(
    state: Mapping[str, object], facts: GitFacts, template: str
) -> str:
    """Fill each required template token exactly once with validated local facts."""
    validated_state = _validate_state(dict(state))
    found = _TOKEN_PATTERN.findall(template)
    if set(found) != set(TEMPLATE_TOKENS) or any(found.count(token) != 1 for token in TEMPLATE_TOKENS):
        raise HandoffError("Invalid handoff template.")
    if "{{" in _TOKEN_PATTERN.sub("", template) or "}}" in _TOKEN_PATTERN.sub("", template):
        raise HandoffError("Invalid handoff template.")
    replacements = {
        "HANDOFF_TIMESTAMP": str(validated_state["updated_at"]),
        "OBJECTIVE": str(validated_state["objective"]),
        "STAGE": str(validated_state["stage"]),
        "ACTIVE_TASK": str(validated_state["active_task"]),
        "TASK_BRIEF": str(validated_state["task_brief"]),
        "FIRST_INCOMPLETE_ACTION": str(validated_state["first_incomplete_action"]),
        "LATEST_RESULT": str(validated_state["latest_result"]),
        "EXPECTED_VERIFICATION": _list_block(validated_state["expected_verification"]),
        "AUTHORIZATION_GATES": _list_block(validated_state["authorization_gates"]),
        "PROHIBITED_ACTIONS": _list_block(validated_state["prohibited_actions"]),
        "INCOMPLETE_WORK_ORIGIN": str(validated_state["incomplete_work_origin"]),
        "NEXT_ACTION": str(validated_state["next_action"]),
        "ORCHESTRATION": _orchestration_block(validated_state["orchestration"]),
        "REVIEW": _review_block(validated_state["review"]),
        "REPOSITORY_ROOT": facts.repository_root.as_posix(),
        "WORKTREE": facts.worktree.as_posix(),
        "BRANCH": facts.branch,
        "HEAD": facts.head,
        "CLEAN": "yes" if facts.clean else "no",
        "STATUS_LINES": _code_block(facts.status_lines),
        "STAGED_FILES": _list_block(list(facts.staged_files)),
        "UNSTAGED_FILES": _list_block(list(facts.unstaged_files)),
        "UNTRACKED_FILES": _list_block(list(facts.untracked_files)),
        "STAGED_DIFF_STAT": _code_block(facts.staged_diff_stat),
        "UNSTAGED_DIFF_STAT": _code_block(facts.unstaged_diff_stat),
        "REMOTES": _list_block(list(facts.remotes)),
        "BOOTSTRAP_PROMPT": _bootstrap_prompt(),
    }
    rendered = template
    for token in TEMPLATE_TOKENS:
        rendered = rendered.replace(f"{{{{{token}}}}}", replacements[token])
    if "{{" in rendered or "}}" in rendered or _has_durable_credential(rendered):
        raise HandoffError("Unsafe rendered handoff.")
    output = rendered if rendered.endswith("\n") else f"{rendered}\n"
    try:
        if len(output.encode("utf-8")) > MAX_RENDERED_UTF8_BYTES:
            raise HandoffError("Rendered handoff exceeds output bounds.")
    except UnicodeEncodeError:
        raise HandoffError("Rendered handoff is not valid UTF-8.") from None
    return output


def _include_prospective_output(
    facts: GitFacts,
    output: Path,
    content: str,
) -> GitFacts:
    """Make pre-write facts describe the output's deterministic post-write state."""
    try:
        existing = output.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = None
    except (OSError, UnicodeDecodeError):
        raise HandoffError("Unable to inspect existing handoff.") from None
    if existing == content:
        return facts

    relative = output.relative_to(facts.repository_root).as_posix()
    if relative in facts.untracked_files:
        return facts

    tracked = bool(
        _decode_git(
            _run_git(facts.repository_root, "ls-files", "--cached", "--", relative)
        ).strip()
    )
    if not tracked:
        return replace(
            facts,
            status_lines=tuple(sorted((*facts.status_lines, f"?? {relative}"))),
            untracked_files=tuple(sorted((*facts.untracked_files, relative))),
        )

    status_lines = list(facts.status_lines)
    for index, line in enumerate(status_lines):
        if len(line) >= 4 and line[3:] == relative:
            status_lines[index] = f"{line[0]}M {relative}"
            break
    else:
        status_lines.append(f" M {relative}")
    other_unstaged_stat = _bounded_stat(
        facts.repository_root,
        "diff",
        "--stat",
        "--no-ext-diff",
        "--",
        ".",
        f":(exclude){relative}",
    )
    stat_note = f" {relative} | excludes generated operational handoff"
    unstaged_stat = (
        f"{other_unstaged_stat}\n{stat_note}" if other_unstaged_stat else stat_note
    )
    return replace(
        facts,
        status_lines=tuple(sorted(status_lines)),
        unstaged_files=tuple(sorted({*facts.unstaged_files, relative})),
        unstaged_diff_stat=unstaged_stat,
    )


def atomic_write(path: Path, content: str) -> None:
    """Replace a handoff only after a durable owner-only temporary write."""
    destination = path.resolve(strict=False)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = parent / f".{destination.name}.refresh-handoff.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        directory_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()
        raise


def refresh(repo: Path, state_path: Path, template_path: Path, output_path: Path) -> None:
    """Validate all inputs then atomically refresh one contained handoff file."""
    facts = collect_git_facts(repo)
    output = output_path.resolve(strict=False)
    if not output.is_relative_to(facts.repository_root):
        raise HandoffError("Handoff output is outside the repository.")
    try:
        template = template_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise HandoffError("Unable to read handoff template.") from None
    state = load_state(state_path)
    initial = render_handoff(state, facts, template)
    final_facts = _include_prospective_output(facts, output, initial)
    atomic_write(output, render_handoff(state, final_facts, template))


def main(argv: Sequence[str] | None = None) -> int:
    """Refresh the handoff from explicit local paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        refresh(args.repo, args.state, args.template, args.output)
    except (HandoffError, OSError):
        print("Handoff refresh failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
