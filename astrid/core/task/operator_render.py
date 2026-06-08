"""Task operator human-readable rendering and audit helpers.

Extracted from ``operator_view.py`` (M4 T60) to keep both modules under the
1,200-line threshold.  This module owns instruction rendering, step progress,
for_each autoclose audit, tail-dispatch, ack templates, and post-completion
handoff helpers.

``operator_view.py`` re-imports every public name from here so existing
callers (``cmd_status``, ``cmd_next``, ``lifecycle``, ``lifecycle_ack``) and
test monkeypatch seams continue to work through the
``astrid.core.task.operator_view`` namespace.
"""

from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from astrid.core.contracts.run_status import STEP_TERMINAL_KINDS
from astrid.core.env_vars import ASTRID_STRICT_INSTRUCTION_SUBST
from astrid.core.project.paths import resolve_projects_root
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    find_step_by_path,
    is_attested_kind,
    is_leaf_step,
    iter_steps_with_path,
)
from astrid.core.task.run_state import _run_is_complete
from astrid.core.task.run_store import _emit_run_completed_if_needed

_PROGRESS_TERMINAL_KINDS = STEP_TERMINAL_KINDS


def _leaf_progress(plan, events: Sequence[dict]) -> tuple[int, int]:
    """Return (completed_leaves, total_leaves) for a quick progress line.

    Total counts every leaf path in the plan tree (repeat expansion ignored —
    a for_each host contributes 1, not N). Completed counts distinct leaf
    paths with a terminal event.
    """
    total_paths: set[tuple[str, ...]] = set()
    for path_tuple, step in iter_steps_with_path(plan):
        if is_leaf_step(step):
            total_paths.add(path_tuple)
    done_paths: set[tuple[str, ...]] = set()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") not in _PROGRESS_TERMINAL_KINDS:
            continue
        raw_path = ev.get("plan_step_path")
        if isinstance(raw_path, list) and raw_path:
            done_paths.add(tuple(raw_path))
            continue
        plan_step_id = ev.get("plan_step_id")
        if isinstance(plan_step_id, str) and plan_step_id:
            done_paths.add(tuple(plan_step_id.split(STEP_PATH_SEP)))
    # Clamp to plan paths in case an event references a stale path.
    done_paths &= total_paths
    return len(done_paths), len(total_paths)


def _emit_for_each_autoclose_audit(plan, events: Sequence[dict]) -> None:
    """Observational audit (T10 / scope-2): for every ``repeat.for_each`` host
    whose items are all attested, warn on stderr if no host ``step_attested``
    is present. Pure observation — never appends an event, never changes the
    exit code. Surfaces Phase-1 autoclose regressions without depending on the
    full regression-audit harness.
    """
    expected: dict[tuple[str, ...], int | None] = {}
    for path_tuple, step in iter_steps_with_path(plan):
        repeat = getattr(step, "repeat", None)
        if isinstance(repeat, RepeatForEach):
            if repeat.items_source == "static":
                expected[path_tuple] = len(repeat.items)
            else:
                expected[path_tuple] = None  # resolved via for_each_expanded
    if not expected:
        return
    item_attested_counts: dict[tuple[str, ...], int] = {p: 0 for p in expected}
    host_step_attested: set[tuple[str, ...]] = set()
    for_each_expanded_total: dict[tuple[str, ...], int] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = ev.get("kind")
        raw_path = ev.get("plan_step_path")
        path_tuple = tuple(raw_path) if isinstance(raw_path, list) else None
        if kind == "item_attested" and path_tuple in item_attested_counts:
            item_attested_counts[path_tuple] += 1
        elif kind == "for_each_expanded" and path_tuple in expected:
            ids = ev.get("item_ids")
            if isinstance(ids, list):
                for_each_expanded_total[path_tuple] = len(ids)
        elif kind == "step_attested":
            plan_step_id = ev.get("plan_step_id")
            if isinstance(plan_step_id, str):
                host_step_attested.add(tuple(plan_step_id.split(STEP_PATH_SEP)))
    for path_tuple, static_total in expected.items():
        total = for_each_expanded_total.get(path_tuple, static_total)
        if total is None or total <= 0:
            continue
        if item_attested_counts.get(path_tuple, 0) != total:
            continue
        if path_tuple in host_step_attested:
            continue
        host_path = STEP_PATH_SEP.join(path_tuple)
        print(
            f"status: host {host_path} appears closed at item level but lacks "
            f"step_attested — possible autoclose regression",
            file=sys.stderr,
        )


_ASTRID_PLACEHOLDER_RE = __import__("re").compile(r"\$\{?(ASTRID_[A-Z_]+)\}?")


def _default_projects_root() -> Path:
    return resolve_projects_root()


def render_step_instructions(
    text: str | None,
    *,
    projects_root: Path | None,
    slug: str,
    run_id: str,
    plan_step_path: tuple[str, ...] | None,
    item_id: str | None,
    iteration: int | None,
) -> str:
    """Canonical instruction renderer (FLAG-S1-001 / issue_hints-2 / all_locations-1).

    Substitutes the full ``$ASTRID_TASK_*`` surface — including the ``${VAR}``
    form — against the resolved run/item context. ``projects_root`` resolution
    order: function param > ``ASTRID_PROJECTS_ROOT`` env > ``resolve_projects_root()``.

    Under ``is_author_test_mode()`` OR ``ASTRID_STRICT_INSTRUCTION_SUBST=1``,
    an unknown ``$ASTRID_*`` token raises ``AssertionError`` and the result is
    post-checked to contain zero ``$ASTRID_`` substrings. In production an
    unknown token is left literal (best-effort, never crashes the CLI).
    """
    import os as _os

    from astrid.core.task.env import is_author_test_mode as _is_author_test_mode

    if text is None:
        return ""
    if projects_root is None:
        projects_root = _default_projects_root()
    step_path_str = STEP_PATH_SEP.join(plan_step_path) if plan_step_path else ""
    allow = {
        "ASTRID_PROJECTS_ROOT": str(projects_root),
        "ASTRID_TASK_PROJECT": slug,
        "ASTRID_TASK_RUN_ID": run_id,
        "ASTRID_TASK_ITEM_ID": item_id or "",
        "ASTRID_TASK_ITERATION": str(iteration) if iteration is not None else "",
        "ASTRID_TASK_STEP_PATH": step_path_str,
    }
    strict = _is_author_test_mode() or _os.environ.get(ASTRID_STRICT_INSTRUCTION_SUBST) == "1"

    def _sub(match):
        token = match.group(1)
        if token in allow:
            return allow[token]
        if strict:
            raise AssertionError(
                f"render_step_instructions: unknown $ASTRID_* token {token!r}"
            )
        return match.group(0)

    result = _ASTRID_PLACEHOLDER_RE.sub(_sub, text)
    if strict:
        assert "$ASTRID_" not in result, (
            f"render_step_instructions: unresolved $ASTRID_ tokens remain in {result!r}"
        )
    return result


def _format_schema_requirements(step) -> str:
    """Extract required keys from a step's json_schema produces and format
    a single human-readable line. Returns empty string when no produces or
    no schema-typed checks.

    Polish #29 — flagged by every v3/v4/v5/v6 probe agent on the
    schema_strict step: the printed instructions listed only some of the
    required keys, the verifier rejected for missing ones, and the agent
    had to dig into plan.json to discover the actual schema. Now the
    instruction printer auto-surfaces required keys per produces entry so
    the instructions and the verifier can't drift.
    """
    produces = getattr(step, "produces", ())
    if not produces:
        return ""
    lines: list[str] = []
    for entry in produces:
        check = getattr(entry, "check", None)
        if check is None or check.check_id != "json_schema":
            continue
        params = getattr(check, "params", {}) or {}
        schema = params.get("schema") if isinstance(params, dict) else None
        # canonical_check_params may have nested the schema under "schema"
        # OR inlined the params. Handle both shapes defensively.
        if not isinstance(schema, dict):
            schema = params if isinstance(params, dict) else {}
        required = schema.get("required") if isinstance(schema, dict) else None
        if not isinstance(required, list) or not required:
            continue
        keys = ", ".join(str(k) for k in required)
        lines.append(f"required keys for {entry.name}: {keys}")
    if not lines:
        return ""
    return "\n".join(lines)


def _identity_parts(identity: str | None) -> tuple[str, str] | None:
    if identity is None:
        return None
    if identity.startswith("agent:") and len(identity) > len("agent:"):
        return "agent", identity[len("agent:"):]
    if identity.startswith("human:") and len(identity) > len("human:"):
        return "human", identity[len("human:"):]
    return None


def _ack_identity_token(
    *, step, ack_kind: str, claimed_identity: str | None
) -> str:
    claimed = _identity_parts(claimed_identity)
    assignee = _identity_parts(getattr(step, "assignee", None))
    if claimed is not None and claimed[0] == ack_kind:
        return f"--{claimed[0]} {claimed[1]}"
    if assignee is not None and assignee[0] == ack_kind:
        return f"--{assignee[0]} {assignee[1]}"
    return "--agent <id>" if ack_kind == "agent" else "--human <name>"


def _ack_template_parts(
    *, path_str: str, slug: str, step, claimed_identity: str | None, has_repeat_for_each: bool
) -> _AckTemplate:
    ack_kind = step.ack.kind if step.ack is not None else "agent"
    identity = _ack_identity_token(
        step=step, ack_kind=ack_kind, claimed_identity=claimed_identity
    )
    base = (
        f"astrid ack {path_str} --project {slug} --decision approve "
        f"{identity} [--evidence path ...]"
    )
    if has_repeat_for_each:
        base += " [--item <id>]"
    return _AckTemplate(command=base)


def _format_ack_template(
    *, path_str: str, slug: str, step, claimed_identity: str | None, has_repeat_for_each: bool
) -> str:
    return _ack_template_parts(
        path_str=path_str,
        slug=slug,
        step=step,
        claimed_identity=claimed_identity,
        has_repeat_for_each=has_repeat_for_each,
    ).command


def _format_claim_line(*, step, claimed_identity: str | None) -> str:
    parts = [f"assignee: {getattr(step, 'assignee', 'system')}"]
    if claimed_identity is not None:
        parts.append(f"claimed: {claimed_identity}")
    return "  ".join(parts)


def _command_has_project_arg(command: str | None) -> bool:
    if not command:
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return any(part == "--project" or part.startswith("--project=") for part in parts)


@dataclass(frozen=True)
class _RewindRetry:
    reason: str
    path: tuple[str, ...]


@dataclass(frozen=True)
class _HostCloseHint:
    host_path: tuple[str, ...]


@dataclass(frozen=True)
class _RunComplete:
    pass


NEXT_JSON_SCHEMA: dict[str, str] = {
    "schema_version": "int: currently 1",
    "project": "str|null: resolved project slug",
    "run_id": "str|null: active run id",
    "state": "str: coarse lifecycle state",
    "action": "str|null: machine-readable action kind",
    "command": "str|null: exact shell command to run next",
    "step": "str|null: current step path",
    "blocked": "bool: true when no immediate progress command is available",
    "reason": "str|null: compact explanation for the selected action",
}


@dataclass(frozen=True)
class _AckTemplate:
    command: str


def _has_host_step_attested(events, host_path_tuple) -> bool:
    path_str = STEP_PATH_SEP.join(host_path_tuple)
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") == "step_attested" and ev.get("plan_step_id") == path_str:
            return True
    return False


def _expected_for_each_total(plan, events, host_path_tuple) -> int | None:
    """Expected total items for a for_each host. Prefers ``for_each_expanded``
    event (covers items_source='from'); falls back to static repeat.items.
    """
    path_list = list(host_path_tuple)
    for ev in events:
        if (
            isinstance(ev, dict)
            and ev.get("kind") == "for_each_expanded"
            and ev.get("plan_step_path") == path_list
        ):
            raw = ev.get("item_ids") or []
            if isinstance(raw, list):
                return len(raw)
            break
    host = find_step_by_path(plan, host_path_tuple)
    host_repeat = getattr(host, "repeat", None) if host is not None else None
    if isinstance(host_repeat, RepeatForEach) and host_repeat.items_source == "static":
        return len(host_repeat.items)
    return None


def _dispatch_from_tail(
    plan,
    events,
    peek,
    *,
    slug: str,
    run_id: str,
    events_path: Path,
    projects_root: Optional[Path],
):
    """Tail-dispatch in ``cmd_next``: derive the next operator-facing action
    from ``events.jsonl``'s tail rather than from ``plan[cursor]`` alone.

    Read-only contract: this helper MUST NOT mutate events EXCEPT for the
    single allowed ``run_completed`` append routed through
    ``_emit_run_completed_if_needed`` (FLAG-S1-007 / correctness-4). Per
    SD-002 (FLAG-S1-002 / correctness-3): we key the rewind branch on
    ``cursor_rewind`` alone — a separate ``produces_check_failed`` branch
    would be dead code because ``_run_inline_checks`` always emits
    ``produces_check_failed`` then ``cursor_rewind`` back-to-back; we read
    the reason from ``events[-2]`` when applicable.
    """
    if not events:
        return None
    last = events[-1] if isinstance(events[-1], dict) else None
    if last is None:
        return None
    last_kind = last.get("kind")

    # (1) Rewind retry — normal inline failures end with cursor_rewind;
    # per-item iteration inline failures end with iteration_failed.
    if last_kind in {"cursor_rewind", "iteration_failed"}:
        # Lazy import to avoid circular dep (operator_view imports from us)
        from astrid.core.task.operator_view import (
            _format_inline_failure_tail,
            _inline_failure_tail,
            _path_tuple_from_event,
        )
        detail = _inline_failure_tail(events)
        if detail is not None:
            return _RewindRetry(
                reason=_format_inline_failure_tail(detail),
                path=detail.path or (peek.path_tuple if peek.path_tuple else ()),
            )
        if last_kind == "iteration_failed" and last.get("reason") == "iterate_feedback":
            return None
        reason = str(last.get("reason") or "previous attempt rewound")
        path_tuple = _path_tuple_from_event(last) or (peek.path_tuple if peek.path_tuple else ())
        return _RewindRetry(reason=reason, path=path_tuple)

    # (2) Host-close hint — defensive belt for replays missing Phase-1
    # autoclose. Only fires when items are exhausted at the item level but
    # the host step_attested is absent.
    if last_kind == "item_attested":
        path_raw = last.get("plan_step_path")
        if isinstance(path_raw, list):
            host_path = tuple(str(p) for p in path_raw)
            expected = _expected_for_each_total(plan, events, host_path)
            host_path_str = STEP_PATH_SEP.join(host_path)
            completed = _completed_items_from_events(events, host_path_str)
            if (
                expected is not None
                and len(completed) >= expected
                and not _has_host_step_attested(events, host_path)
            ):
                return _HostCloseHint(host_path=host_path)

    # (3) Run-complete — emit run_completed via the centralized helper.
    if peek.exhausted and _run_is_complete(plan, events):
        _emit_run_completed_if_needed(
            plan, events, events_path, run_id,
            slug=slug, projects_root=projects_root,
        )
        return _RunComplete()

    return None


def _completed_items_from_events(events, host_path):
    """Return the set of item ids that have a completed/attested event under
    ``host_path``. ``host_path`` is the STEP_PATH_SEP-joined string form.
    """
    path_list = host_path.split(STEP_PATH_SEP) if host_path else []
    completed: set[str] = set()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = ev.get("kind")
        if kind not in ("item_completed", "item_attested"):
            continue
        if ev.get("plan_step_path") != path_list:
            continue
        item_id = ev.get("item_id")
        if isinstance(item_id, str):
            completed.add(item_id)
    return completed


def _print_post_completion_handoff(
    slug: str,
    *,
    just_finished_plan_id: str | None,
    packs_root: Optional[Path] = None,
) -> None:
    """Fix 3 (v6 dogfood): after a run completes, print the next concrete
    orchestrator the agent should start.

    Lists available orchestrators on the checkout, filters out the one that
    just completed (so we don't suggest "do the same thing again"), and
    surfaces the freshest remaining id with the canonical ``astrid start``
    invocation. When nothing else is registered, falls back to a generic
    template plus the ``astrid next`` suggestion shell so the agent still
    has a single legal command to type.
    """
    from astrid.core.task.orchestrator_resolver import _list_orchestrator_ids

    orchs, _ = _list_orchestrator_ids(packs_root=packs_root)
    others = [oid for oid in orchs if oid != just_finished_plan_id]
    print()
    print("start another orchestrator on this project:")
    if others:
        top = others[0]
        print(f"  astrid start {top} --project {slug}")
        if len(others) > 1:
            print(
                f"  # other candidates: {', '.join(others[1:])}"
            )
    else:
        print(f"  astrid start <orchestrator-id> --project {slug}")
    print("(or just run `astrid next` for a fresh suggestion list)")
