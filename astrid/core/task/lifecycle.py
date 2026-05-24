"""Phase 5 lifecycle verbs: start/abort/status/runs ls/next; cmd_ack lives
in lifecycle_ack.py to keep both modules under the size budget.

cmd_runs_ls (FLAG-P5-006): natural completion does not clear active_run.json
in V1, so the lister surfaces only 'aborted' vs 'in-progress'.
cmd_start (SD-007): does not silently invoke compile when the pre-built JSON
manifest is missing — prints the compile recovery and returns non-zero.
"""

from __future__ import annotations

import argparse
import json
import shlex
import secrets
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional, Sequence

from astrid.core.project.jsonio import write_json_atomic
from astrid.core.project.project import ProjectError, require_project
from astrid.core.project.paths import (
    project_dir,
    resolve_projects_root,
    validate_project_slug,
    validate_run_id,
)
from astrid.core.project.current_run import (
    clear_current_run,
    read_current_run,
    read_current_run_state,
    write_current_run,
)
from astrid.core.session.lease import (
    read_lease,
    release_writer_lease,
    write_lease_init,
)
from astrid.core.session.writer import writer_context_for_project
from astrid.core.task.env import task_actor_env
from astrid.core.task.events import (
    EventLogError,
    _run_is_complete,
    make_run_aborted_event,
    make_run_completed_event,
    make_run_started_event,
    make_step_awaiting_fetch_event,
    make_step_completed_event,
    read_events,
)
from astrid.core.task.gate import TaskRunGateError, peek_current_step
from astrid.core.task.inbox import consume_inbox_entry, pending_count, scan_inbox
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    Step,
    is_attested_kind,
    is_code_kind,
    is_group_step,
    is_leaf_step,
    iter_steps_with_path,
    compute_plan_hash,
    load_plan,
    step_dir_for_path,
)
from astrid.core.task.preamble import PROHIBITION_PREAMBLE
from astrid.core.timeline.defaults import read_project_default
from astrid.core.timeline.paths import find_timeline_by_slug, find_timeline_slug_for_ulid


_AGENT_MD_TEMPLATE = """{preamble}

QUALIFIED ORCHESTRATOR: {qualified_id}
RUN ID: {run_id}
TIMELINE ID: {timeline_id}

FIRST COMMAND (Sprint 1 / T15)
- astrid status                    # session breadcrumb; ALWAYS run first
- astrid attach {slug}     # bind this tab to {slug} if status reports unbound

RECOVERY COMMANDS
- See next legal action:    astrid next --project {slug}
- Acknowledge attested:     astrid ack <step> --project {slug} --decision approve [--agent <id> | --actor <name>]
- View run state:           astrid status --project {slug}
- End the run:              astrid abort --project {slug}
- Take over a stuck run:    astrid sessions takeover <run-id|session-id>
- Detach the current tab:   astrid sessions detach

STOP HOOK
- The `astrid hook stop` command is the Claude Code Stop-hook entry point.
  When wired into .claude/settings.json (see docs/HOOKS.md) it re-injects this
  preamble and the current step on every Stop boundary so the rules above
  stay live for the entire run. The hook is a silent no-op outside task mode.

INBOX SURFACE
- External processes (humans, scripts, other tools) signal completion of an
  attested step by dropping a JSON file into runs/{run_id}/inbox/.
- File shape:
    {{
      "step_id": "<id of the current attested step>",
      "decision": "approve" | "retry" | "abort",
      "evidence": {{ "<key>": "<non-empty string>", ... }},
      "submitted_at": "<ISO 8601 timestamp>",
      "submitted_by": "<external system or operator name>",
      "item_id": "<optional for_each item id>"
    }}
- Consume-on-next: astrid next reads inbox/, validates each file against
  the current cursor, and appends a step_attested / item_attested /
  cursor_rewind / run_aborted event before computing the next step.
- Agent attestations only — actor-ack steps must use `astrid ack` (the
  inbox file would be quarantined to inbox/.rejected/ otherwise).
- WARNING: `astrid next` is state-mutating when inbox/ has files.
"""


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _system_exit_code(exc: SystemExit) -> int:
    return int(exc.code) if isinstance(exc.code, int) else 2


def _resolve_packs_root(packs_root: Optional[Path]) -> Path:
    if packs_root is not None:
        return Path(packs_root)
    from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT
    return DEFAULT_PACKS_ROOT


def _qualified_split(qualified_id: str) -> tuple[str, str]:
    if not isinstance(qualified_id, str) or "." not in qualified_id:
        raise ValueError(
            f"orchestrator id {qualified_id!r} must be '<pack>.<name>'"
        )
    pack, _, name = qualified_id.partition(".")
    if not pack or not name or "." in name:
        raise ValueError(
            f"orchestrator id {qualified_id!r} must be exactly '<pack>.<name>'"
        )
    return pack, name


def _generate_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{secrets.token_hex(4)}"


# ---------------------------------------------------------------------------
# cmd_start
# ---------------------------------------------------------------------------


def cmd_start(
    argv: Sequence[str],
    *,
    packs_root: Optional[Path] = None,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid start", add_help=True)
    parser.add_argument("orchestrator_id", help="qualified id <pack>.<name>")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--name", default=None, help="optional run id (slug-validated)")
    parser.add_argument("--timeline", default=None, help="timeline slug")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        _print_err(f"start: {exc}")
        return 1
    try:
        require_project(slug, root=projects_root)
    except ProjectError:
        _print_err(
            f"start: project {slug!r} not found; "
            f"create one with `astrid projects create {slug}`"
        )
        return 1

    try:
        pack, name = _qualified_split(args.orchestrator_id)
    except ValueError as exc:
        _print_err(f"start: {exc}")
        return 1

    if read_current_run(slug, root=projects_root) is not None:
        _print_err(
            f"start: active run already exists for project {slug!r}; "
            f"recovery: astrid abort --project {slug}"
        )
        return 1

    packs = _resolve_packs_root(packs_root)
    build_path = packs / pack / "build" / f"{name}.json"
    if not build_path.is_file():
        _print_err(
            f"start: compiled plan not found at {build_path}; "
            f"recovery: astrid author compile {args.orchestrator_id}"
        )
        return 1

    try:
        compiled_payload = json.loads(build_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _print_err(f"start: failed to read {build_path}: {exc}")
        return 1

    # Resolve timeline ULID (timeline_id) and slug for display.
    timeline_id: str | None = None
    timeline_slug: str | None = None
    if args.timeline is not None:
        found = find_timeline_by_slug(slug, args.timeline, root=projects_root)
        if found is None:
            _print_err(
                f"start: timeline {args.timeline!r} not found in project {slug!r}"
            )
            return 1
        timeline_id = found[0]
        timeline_slug = args.timeline
    else:
        default_ulid = read_project_default(slug, root=projects_root)
        if default_ulid is not None:
            resolved_slug = find_timeline_slug_for_ulid(slug, default_ulid, root=projects_root)
            if resolved_slug is not None:
                timeline_id = default_ulid
                timeline_slug = resolved_slug
                _print_err(
                    f"Using default timeline: {timeline_slug}. "
                    f"Use --timeline to override."
                )
    # If still no timeline, list available timelines and error when a choice is
    # needed; a project with zero timelines can still start a task run.
    if timeline_id is None:
        from astrid.core.timeline.crud import list_timelines
        available = list_timelines(slug, root=projects_root)
        if available:
            _print_err("No default timeline; pass --timeline <slug>. Available:")
            for ts in available:
                _print_err(f"  {ts.slug}  ({ts.name})")
            return 1
        else:
            _print_err(
                f"start: no timelines exist for project {slug!r}; "
                "starting without a timeline. "
                f"Create one later with `astrid timelines create <slug>`."
            )

    proj_root = project_dir(slug, root=projects_root)
    proj_root.mkdir(parents=True, exist_ok=True)
    plan_path = proj_root / "plan.json"
    write_json_atomic(plan_path, compiled_payload)

    try:
        load_plan(plan_path)
    except Exception as exc:
        _print_err(f"start: compiled plan failed validation: {exc}")
        return 1

    plan_hash = compute_plan_hash(plan_path)

    if args.name is not None:
        try:
            run_id = validate_run_id(args.name)
        except Exception as exc:
            _print_err(f"start: --name {exc}")
            return 1
    else:
        run_id = _generate_run_id()

    run_dir = proj_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Lease-first ordering: any reader that observes current_run.json is
    # guaranteed to find a corresponding lease.json. The session id on the
    # lease is whatever ASTRID_SESSION_ID resolves to (CLI gate enforces
    # the session is bound before cmd_start dispatch); fall back to
    # 'legacy' for non-CLI callers that haven't migrated yet (tests etc).
    from astrid.core.session.binding import (
        SessionBindingError,
        resolve_current_session,
    )

    session_id_for_lease = "legacy"
    try:
        # T9 / FLAG-S1-003: pass slug for file-bound .astrid-session fallback.
        bound = resolve_current_session(slug=slug)
        if bound is not None:
            session_id_for_lease = bound.id
    except SessionBindingError:
        session_id_for_lease = "legacy"
    write_lease_init(
        run_dir,
        session_id=session_id_for_lease,
        plan_hash=plan_hash,
        timeline_id=timeline_id,
    )
    write_current_run(slug, run_id, root=projects_root)

    events_path = run_dir / "events.jsonl"
    actor = task_actor_env()
    with writer_context_for_project(slug, root=projects_root) as writer:
        writer.append(make_run_started_event(run_id, plan_hash, actor=actor))

    agent_md = _AGENT_MD_TEMPLATE.format(
        preamble=PROHIBITION_PREAMBLE,
        qualified_id=args.orchestrator_id,
        run_id=run_id,
        slug=slug,
        timeline_id=timeline_id,
    )
    (run_dir / "AGENT.md").write_text(agent_md, encoding="utf-8")

    print(f"started {args.orchestrator_id}")
    print(f"  project:   {slug}")
    print(f"  timeline:  {timeline_slug}")
    print(f"  run-id:    {run_id}")
    print(f"  plan-hash: {plan_hash}")
    return 0


# ---------------------------------------------------------------------------
# cmd_abort
# ---------------------------------------------------------------------------


def cmd_abort(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid abort", add_help=True)
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--reason", default=None, help="optional human-readable reason")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        _print_err(f"abort: {exc}")
        return 1

    run_id = read_current_run(slug, root=projects_root)
    if run_id is None:
        # Idempotent — Phase 6 Stop-hook may invoke abort defensively.
        return 0

    run_dir = project_dir(slug, root=projects_root) / "runs" / run_id
    with writer_context_for_project(slug, root=projects_root) as writer:
        writer.append(make_run_aborted_event(run_id, reason=args.reason))
    # DEC-010: clear the pointer AND release the writer lease so the run
    # is fully detached. A follow-up takeover would now see the lease as
    # orphan-pending.
    clear_current_run(slug, root=projects_root)
    try:
        release_writer_lease(run_dir)
    except FileNotFoundError:
        pass
    print(f"aborted {run_id}")
    return 0


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


def _leaf_progress(plan, events: Sequence[dict]) -> tuple[int, int]:
    """Return (completed_leaves, total_leaves) for a quick progress line.

    Total counts every leaf path in the plan tree (repeat expansion ignored —
    a for_each host contributes 1, not N). Completed counts distinct leaf
    paths with a terminal event: step_completed, step_attested, or step_skipped.
    """
    total_paths: set[tuple[str, ...]] = set()
    for path_tuple, step in iter_steps_with_path(plan):
        if is_leaf_step(step):
            total_paths.add(path_tuple)
    terminal_kinds = {"step_completed", "step_attested", "step_skipped"}
    done_paths: set[tuple[str, ...]] = set()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") not in terminal_kinds:
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


def cmd_status(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid status", add_help=True)
    parser.add_argument("--project", required=True, help="project slug")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        _print_err(f"status: {exc}")
        return 1

    active_run = read_current_run_state(slug, root=projects_root)
    if active_run is None:
        _print_err(
            f"status: no active run for project {slug!r}; "
            f"recovery: astrid start <orchestrator-id> --project {slug}"
        )
        return 1

    run_id = active_run["run_id"]
    plan_hash = active_run["plan_hash"]
    proj_root = project_dir(slug, root=projects_root)
    plan_path = proj_root / "plan.json"
    events_path = proj_root / "runs" / run_id / "events.jsonl"

    plan = load_plan(plan_path)
    events = read_events(events_path)
    peek = peek_current_step(
        plan, events, slug, project_root=proj_root, run_id=run_id
    )

    print(f"run-id:    {run_id}")
    print(f"plan-hash: {plan_hash}")
    completed, total = _leaf_progress(plan, events)
    print(f"progress:  {completed} of {total} steps complete")
    _emit_for_each_autoclose_audit(plan, events)
    if peek.exhausted or peek.step is None:
        print("current:   <run exhausted>")
    else:
        path_str = STEP_PATH_SEP.join(peek.path_tuple)
        kind = "nested" if is_group_step(peek.step) else (
            "attested" if is_attested_kind(peek.step) else "code"
        )
        suffix = ""
        if peek.iteration is not None:
            suffix += f"  iter={peek.iteration}"
        if peek.item_id is not None:
            suffix += f"  item={peek.item_id}"
        print(f"current:   {path_str} [{kind}] v{peek.step.version}{suffix}")
        if peek.step.produces:
            names = ", ".join(p.name for p in peek.step.produces)
            print(f"produces:  {names}")

    pending = pending_count(proj_root / "runs" / run_id)
    if pending > 0:
        print(f"inbox:     {pending} pending")

    print("recent events:")
    for ev in events[-5:]:
        kind = ev.get("kind", "?")
        ts = ev.get("ts", "")
        plan_step_id = ev.get("plan_step_id")
        if not isinstance(plan_step_id, str):
            path = ev.get("plan_step_path")
            plan_step_id = "/".join(path) if isinstance(path, list) else ""
        print(f"  {ts}  {kind}  {plan_step_id}")
    return 0


# ---------------------------------------------------------------------------
# cmd_next
# ---------------------------------------------------------------------------


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
    strict = _is_author_test_mode() or _os.environ.get("ASTRID_STRICT_INSTRUCTION_SUBST") == "1"

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


def _format_ack_template(
    *, path_str: str, slug: str, ack_kind: str, has_repeat_for_each: bool
) -> str:
    identity = "--agent <id>" if ack_kind == "agent" else "--actor <name>"
    base = (
        f"astrid ack {path_str} --project {slug} --decision approve "
        f"{identity} [--evidence path ...]"
    )
    if has_repeat_for_each:
        base += " [--item <id>]"
    return base


def _find_step_by_path(plan, path_tuple):
    """Walk a TaskPlan to find the step at ``path_tuple`` (descending NestedStep
    children). Returns the step or None if the path does not resolve.
    """
    if not path_tuple:
        return None
    steps = plan.steps
    for segment in path_tuple[:-1]:
        match = next((s for s in steps if s.id == segment), None)
        if match is None or not is_group_step(match):
            return None
        steps = match.children or ()
    return next((s for s in steps if s.id == path_tuple[-1]), None)


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
    host = _find_step_by_path(plan, host_path_tuple)
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

    # (1) Rewind retry — single collapsed branch keyed on cursor_rewind.
    if last_kind == "cursor_rewind":
        reason = "previous attempt rewound"
        if len(events) >= 2 and isinstance(events[-2], dict):
            prior = events[-2]
            if prior.get("kind") == "produces_check_failed":
                reason = str(prior.get("reason") or reason)
            else:
                reason = str(last.get("reason") or reason)
        path_raw = last.get("plan_step_path")
        if isinstance(path_raw, list):
            path_tuple = tuple(str(p) for p in path_raw)
        else:
            path_tuple = peek.path_tuple if peek.path_tuple else ()
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


def _emit_run_completed_if_needed(
    plan,
    events,
    events_path: Path,
    run_id: str,
    *,
    slug: str | None = None,
    projects_root: Optional[Path] = None,
) -> bool:
    """Single source of truth for appending ``run_completed`` (FLAG-S1-007 /
    correctness-4). Idempotent: returns True iff the run is complete AND a
    ``run_completed`` event is present after the call (whether emitted now or
    already on disk). All ``cmd_next`` emit sites MUST route through this
    helper; any new ``make_run_completed_event`` append outside this helper
    half-closes FLAG-S1-007.

    Side effect when ``slug`` is provided (#25): on the first ``run_completed``
    emission (not on idempotent re-entry), also clears the project's
    ``current_run.json`` pointer so a follow-up ``astrid start <next-orch>``
    is unblocked. The lease and run files stay on disk; only the "active
    run" pointer is released. Without this, agents must `astrid abort` to
    switch orchestrators even though the run completed normally — flagged
    by the v4 seq probe.
    """
    for ev in events:
        if isinstance(ev, dict) and ev.get("kind") == "run_completed":
            return True
    if not _run_is_complete(plan, events):
        return False
    with writer_context_for_project(slug, root=projects_root) as writer:
        writer.append(make_run_completed_event(run_id))
    # Release the active-run pointer so the project is free for the next
    # orchestrator. Idempotent guard: only the first call gets past the
    # early-return above, so this fires exactly once per run.
    if slug:
        try:
            clear_current_run(slug, root=projects_root)
        except Exception:
            # Never let pointer cleanup block the run-completed signal.
            # Worst case: agent has to `astrid abort` once before starting
            # the next orchestrator — same as pre-fix behavior.
            pass
    return True


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


def _list_project_slugs(projects_root: Optional[Path]) -> list[str]:
    """List on-disk project slugs at the projects_root (sorted, never raises)."""
    try:
        root = Path(projects_root) if projects_root is not None else resolve_projects_root()
    except Exception:
        return []
    if not root.is_dir():
        return []
    slugs: list[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "project.json").is_file():
            continue
        slugs.append(entry.name)
    return slugs


def _list_orchestrator_ids(packs_root: Optional[Path] = None) -> tuple[list[str], str | None]:
    """List installable orchestrators as qualified ids.

    Returns ``(ids, error_summary)``. On registry-load failure the ids list
    is empty AND ``error_summary`` is a one-line hint pointing at the
    underlying issue so the next-hint can say "registry is broken" instead
    of "nothing installed".

    Two-source union: YAML-manifested orchestrators (via the registry) AND
    DSL-authored orchestrators that have a compiled ``build/<name>.json``
    (which is enough for ``astrid start`` to work but doesn't show up in
    the registry today). The v6 probe found that DSL-compiled orchestrators
    were invisible to `astrid next`'s suggestions even though they ran
    fine — the agent could start them only by knowing their id externally.

    Sort order (polish #30): orchestrators with a recently-modified
    ``build/<name>.json`` first (most recently compiled / used), then
    alphabetical. The v6 probe found ``mini_research`` and ``agent_probe``
    were buried below alphabetically-earlier orchestrators the agent didn't
    want; recency surfaces what the operator just touched.
    """
    ids: set[str] = set()
    registry_err: str | None = None
    try:
        from astrid.core.orchestrator.registry import load_default_registry
        registry = load_default_registry()
        ids.update(o.id for o in registry.list())
    except Exception as exc:
        registry_err = f"{type(exc).__name__}: {exc}"

    # Add DSL-compiled orchestrators discovered from build/*.json files.
    # Each `<pack>/build/<name>.json` corresponds to qualified id
    # `<pack>.<name>`. Defensive — never raises if a pack dir is missing.
    try:
        from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT
        if DEFAULT_PACKS_ROOT.is_dir():
            for pack_dir in DEFAULT_PACKS_ROOT.iterdir():
                if not pack_dir.is_dir():
                    continue
                build_dir = pack_dir / "build"
                if not build_dir.is_dir():
                    continue
                for build_file in build_dir.glob("*.json"):
                    ids.add(f"{pack_dir.name}.{build_file.stem}")
    except Exception:
        pass

    if not ids:
        return [], registry_err

    def _build_mtime(qualified_id: str) -> float:
        if "." not in qualified_id:
            return 0.0
        pack, _, name = qualified_id.partition(".")
        try:
            from astrid.orchestrate.compile import DEFAULT_PACKS_ROOT
            build_path = DEFAULT_PACKS_ROOT / pack / "build" / f"{name}.json"
            return build_path.stat().st_mtime if build_path.is_file() else 0.0
        except Exception:
            return 0.0

    id_list = sorted(ids, key=lambda qid: (-_build_mtime(qid), qid))
    return id_list, registry_err


def _print_next_unbound_hint(
    projects_root: Optional[Path],
    *,
    target_slug: str | None = None,
) -> None:
    """Universal port-of-call (#13): no session bound.

    Print exactly one legal next command. Broader discovery belongs to
    ``astrid status``; ``next`` is the action surface.

    When ``target_slug`` is set (caller passed ``--project <slug>``), the
    hint targets that specific slug instead of listing discovered projects.
    Output deliberately matches the old gate's error wording (``no session
    bound``, ``astrid status``, ``astrid attach``) so existing tests +
    automation that grep stderr keep matching.
    """
    if target_slug:
        action = f"astrid attach {target_slug}"
        print("no session bound.")
        print()
        print("next:")
        print(f"  {action}")
        return

    slugs = _list_project_slugs(projects_root)
    action: str
    try:
        from astrid.core.session.config import resolve_default_project
        default = resolve_default_project()
    except Exception:
        default = None
    if default and default in slugs:
        action = "astrid attach"
    elif len(slugs) == 1:
        action = f"astrid attach {slugs[0]}"
    elif slugs:
        action = "astrid status"
    else:
        action = "astrid projects create <slug>"
    print("no session bound.")
    print()
    print("next:")
    print(f"  {action}")


def _print_next_no_run_hint(slug: str, projects_root: Optional[Path]) -> None:
    """Universal port-of-call (#13): session bound, project attached, but
    no active run. Print the `astrid start` template plus a top-N
    orchestrator suggestion list.
    """
    orchs, registry_err = _list_orchestrator_ids()
    print(f"session bound to {slug!r}, but no active task run.")
    print()
    print("start a new run:")
    print(f"  astrid start <orchestrator-id> --project {slug}")
    print()
    if orchs:
        print("available orchestrators:")
        for oid in orchs:
            print(f"  astrid start {oid} --project {slug}")
    elif registry_err is not None:
        print("orchestrator registry failed to load:")
        print(f"  {registry_err}")
        print("fix the broken manifest then re-run, or browse with "
              "`astrid orchestrators list`.")
    else:
        print("no orchestrators are registered for this checkout; "
              "see `astrid orchestrators list` or `astrid author new <pack>.<name>` "
              "to author one.")


def _os_environ_has_session() -> bool:
    """True iff ASTRID_SESSION_ID is set and non-empty in os.environ."""
    import os as _os
    return bool(_os.environ.get("ASTRID_SESSION_ID", "").strip())


def _most_recent_session_slug(projects_root: Optional[Path]) -> str | None:
    """Find the slug whose .astrid-session file was most recently written.

    Cross-shell session resolution (#24): when an agent has done `astrid
    attach <slug>` in a prior shell but the current shell doesn't have
    ASTRID_SESSION_ID set, scanning projects-root for the freshest
    .astrid-session is a cheap way to recover the same binding.

    Concurrency disambiguation (polish #32, hardened by agentic dogfood
    finding #DD): when multiple agents share one projects-root and each
    writes its own ``.astrid-session``, "the freshest" can be ANY of them,
    not necessarily the one this caller actually attached.

    The original fix (60s ambiguity window) was insufficient. A real
    Claude agent doing the agentic test concurrency probe reported the
    failure mode the 60s window misses: agent A attaches at T+0, agent
    B attaches at T+120 (outside the window), then agent A re-touches
    its ``.astrid-session`` at T+200 (re-attach, status read, whatever).
    Now A's file is fresher than B's, B's bare ``astrid next`` resolves
    to A's project — silently wrong binding. Window-based heuristics
    cannot catch mtime-crossings; they're a fundamental global race.

    Hardened policy: refuse auto-resolve when MORE THAN ONE
    ``.astrid-session`` exists in the projects-root, regardless of
    mtimes. The agent must be explicit (`--project`, `attach`, or
    `ASTRID_SESSION_ID`). Fail closed — the cost of a silently wrong
    binding is much higher than the cost of one extra `--project` flag.

    Single-project case still works: one ``.astrid-session`` → resolve
    it. Multi-project case forces explicit selection.

    This is a deliberate UX fallback in `cmd_next`, distinct from
    `resolve_current_session` itself (which by FLAG-S1-003 invariant
    never walks the filesystem to discover the slug).
    """
    try:
        root = Path(projects_root) if projects_root is not None else resolve_projects_root()
    except Exception:
        return None
    if not root.is_dir():
        return None
    candidates: list[tuple[float, str]] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / "project.json").is_file():
            continue
        session_file = entry / ".astrid-session"
        if not session_file.is_file():
            continue
        try:
            candidates.append((session_file.stat().st_mtime, entry.name))
        except OSError:
            continue
    if not candidates:
        return None
    if len(candidates) > 1:
        # Ambiguous: more than one bound project on disk. Print an
        # enumerated stderr nudge so the caller (often an agent reading
        # stderr) can pick the right project explicitly.
        candidates.sort(key=lambda t: t[0], reverse=True)  # freshest first
        print(
            f"_most_recent_session_slug: {len(candidates)} projects have a"
            f" bound session on disk — refusing to guess.",
            file=sys.stderr,
        )
        for mtime, pslug in candidates:
            print(f"  --project {pslug}", file=sys.stderr)
        return None
    return candidates[0][1]


def cmd_next(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="astrid next",
        add_help=True,
        description=(
            "Universal port-of-call. Prints the single legal action to take, "
            "regardless of where you are: cold (no session), in-session but "
            "no active run, mid-run, or run complete."
        ),
    )
    parser.add_argument(
        "--project",
        required=False,
        default=None,
        help=(
            "project slug; if omitted, derived from the bound session "
            "(ASTRID_SESSION_ID). Without a bound session, prints the "
            "attach/create discovery hint."
        ),
    )
    parser.add_argument(
        "--skip",
        action="store_true",
        help="skip the next step if it is optional=True (loops until a non-optional or exhausted)",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help="optional reason recorded with each --skip event",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    # Always print preamble first, verbatim, every call (SD-023) — even on
    # error / exhausted paths so Stop-hook context re-injection is consistent.
    print(PROHIBITION_PREAMBLE)
    print()

    # Universal port-of-call (#13): derive slug from --project OR the bound
    # session OR fall through to the unbound discovery hint. The agent-UX
    # principle: `astrid next` ALWAYS prints exactly one legal action — never
    # an error that requires the agent to remember which other verb to run.
    slug: str | None = args.project
    explicit_project = slug is not None
    try:
        from astrid.core.session.binding import (
            SessionBindingError,
            resolve_current_session,
        )
        # Cross-shell session resolution (#24/#32): when no slug + no env var,
        # find the most-recently-modified .astrid-session file across the
        # projects-root and use that slug. 4/4 v4 probes flagged "had to
        # manually export ASTRID_SESSION_ID after attach"; the file-bound
        # fallback already exists in resolve_current_session but only fires
        # when a slug is passed. This makes the no-flag astrid next path
        # actually work across shell invocations.
        #
        # When auto-resolve fires we print the source on stderr so the
        # agent can verify the picked slug is what they meant. v7_min
        # surfaced that an agent could silently bind to a stranger's
        # session without realising it; explicit attribution + the
        # ambiguity guard in _most_recent_session_slug together close
        # that gap. Note: stderr so it doesn't pollute the main output
        # that agents parse for action commands.
        auto_resolved_slug: str | None = None
        if slug is None and not _os_environ_has_session():
            auto_resolved_slug = _most_recent_session_slug(projects_root)
            slug = auto_resolved_slug
        session = resolve_current_session(slug=slug)
        if auto_resolved_slug is not None and session is not None:
            _print_err(
                f"(auto-resolved session for project {auto_resolved_slug!r} "
                f"via .astrid-session; pass --project explicitly to override)"
            )
    except SessionBindingError as exc:
        _print_err(f"next: {exc}")
        return 1
    # No resolved session means no task-run action is legal yet. Even with
    # --project, print the single attach action instead of inspecting run
    # state anonymously.
    if session is None:
        _print_next_unbound_hint(
            projects_root,
            target_slug=slug if explicit_project else None,
        )
        return 0
    if slug is None and session is not None:
        slug = session.project

    try:
        slug = validate_project_slug(slug)
    except Exception as exc:
        _print_err(f"next: {exc}")
        return 1

    active_run = read_current_run_state(slug, root=projects_root)
    if active_run is None:
        # SESSION BOUND, NO RUN: print orchestrator suggestions + the
        # exact `astrid start` template the agent should type next.
        _print_next_no_run_hint(slug, projects_root)
        return 0

    run_id = active_run["run_id"]
    proj_root = project_dir(slug, root=projects_root)
    plan_path = proj_root / "plan.json"
    events_path = proj_root / "runs" / run_id / "events.jsonl"
    run_dir = proj_root / "runs" / run_id

    # Universal port-of-call (#18): reader-state detection. The dominant
    # friction in the v3 DS probe (4/5 reports) was agents discovering they
    # were attached as readers via a downstream gate rejection on `ack`.
    # When `astrid next` is the agent's port-of-call, it should surface
    # writer-mismatch BEFORE printing step instructions the agent will then
    # be unable to ack.
    try:
        from astrid.core.session.binding import (
            SessionBindingError as _SBErr,
            is_writer_for,
            resolve_current_session,
        )
        _session = resolve_current_session(slug=slug)
    except _SBErr as exc:
        _print_err(f"next: {exc}")
        return 1
    # The reader-state hint only makes sense if the bound session is
    # actually for THIS project. A session bound to a different project
    # (e.g. the autouse-seed in tests, or an agent mid-context-switch)
    # doesn't make us a "reader" of this project's run — we just don't
    # have any binding to it at all. Skip the warning in that case.
    if (
        _session is not None
        and _session.project == slug
        and not is_writer_for(_session, run_dir)
    ):
        print(f"attached to {slug!r} as reader — another session holds the writer lease.")
        print()
        print("take over the run to advance:")
        print(f"  astrid sessions takeover {run_id}")
        print()
        print("after takeover, run `astrid next` again for the current step.")
        return 0

    # FLAG-P8-005: cmd_next becomes state-mutating when inbox/ contains valid
    # files. Each entry is consumed best-effort so a single bad file cannot
    # crash the verb.
    for entry in scan_inbox(run_dir):
        try:
            consume_inbox_entry(
                run_dir, entry, slug=slug, projects_root=projects_root
            )
        except (TaskRunGateError, OSError, EventLogError):
            continue

    plan = load_plan(plan_path)
    events = read_events(events_path)
    peek = peek_current_step(
        plan, events, slug, project_root=proj_root, run_id=run_id
    )

    # Tail-dispatch (FLAG-S1-002 / correctness-3): derive operator-facing
    # action from events.jsonl's tail. Runs BEFORE --skip handling so a
    # rewind or completed-run signal takes precedence over a skip request.
    # Every return path below has the PROHIBITION_PREAMBLE already printed
    # (line ~723) — SD-023 invariant preserved.
    _tail_render_kwargs = dict(
        projects_root=projects_root,
        slug=slug,
        run_id=run_id,
        plan_step_path=peek.path_tuple if peek.path_tuple else None,
        item_id=peek.item_id,
        iteration=peek.iteration,
    )
    tail_action = _dispatch_from_tail(
        plan,
        events,
        peek,
        slug=slug,
        run_id=run_id,
        events_path=events_path,
        projects_root=projects_root,
    )
    if isinstance(tail_action, _RewindRetry):
        path_str = STEP_PATH_SEP.join(tail_action.path) if tail_action.path else ""
        msg = (
            f"Previous attempt rejected: {tail_action.reason}. "
            f"Re-write the artifact for {path_str!r} and re-ack."
        )
        print(render_step_instructions(msg, **{**_tail_render_kwargs, "plan_step_path": tail_action.path or None}))
        return 0
    if isinstance(tail_action, _HostCloseHint):
        host_path_str = STEP_PATH_SEP.join(tail_action.host_path)
        msg = (
            f"All items complete. Close the host with `astrid ack "
            f"{host_path_str} --project {slug} --decision approve "
            f"--agent <id> --evidence ...` (omit --item)."
        )
        print(render_step_instructions(
            msg,
            **{**_tail_render_kwargs, "plan_step_path": tail_action.host_path, "item_id": None, "iteration": None},
        ))
        return 0
    if isinstance(tail_action, _RunComplete):
        print(render_step_instructions(
            "Run complete. Nothing to do.",
            **{**_tail_render_kwargs, "plan_step_path": None, "item_id": None, "iteration": None},
        ))
        # Fix 3 (v6 dogfood): post-completion handoff was missing on this
        # tail-derived RunComplete path. Mirror the other RunComplete path
        # (~line 1376) so sequential_orchestrators no longer dead-ends.
        _print_post_completion_handoff(
            slug,
            just_finished_plan_id=getattr(plan, "plan_id", None),
        )
        return 0

    # --skip: emit step_skipped events for optional leaves until either the
    # next leaf is non-optional or the cursor exhausts. The very first
    # peek MUST be optional — refusing to start otherwise — but subsequent
    # iterations naturally stop at the first non-optional leaf and fall
    # through to print its dispatch.
    if args.skip:
        if peek.exhausted or peek.step is None:
            _print_err(
                f"next --skip: run is exhausted; recovery: astrid abort --project {slug}"
            )
            return 1
        if not peek.step.optional:
            _print_err(
                f"next --skip: cursor step {STEP_PATH_SEP.join(peek.path_tuple)!r} "
                f"is not optional; remove --skip to dispatch it"
            )
            return 1
        from astrid.core.task.events import make_step_skipped_event
        while (
            not (peek.exhausted or peek.step is None)
            and peek.step.optional
        ):
            skip_event = make_step_skipped_event(
                STEP_PATH_SEP.join(peek.path_tuple),
                actor_kind="agent",
                actor_id="cli",
                reason=args.reason,
            )
            with writer_context_for_project(slug, root=projects_root) as writer:
                writer.append(skip_event)
            print(f"skipped {STEP_PATH_SEP.join(peek.path_tuple)}")
            events = read_events(events_path)
            peek = peek_current_step(
                plan, events, slug, project_root=proj_root, run_id=run_id
            )
        if peek.exhausted or peek.step is None:
            _emit_run_completed_if_needed(
                plan, events, events_path, run_id,
                slug=slug, projects_root=projects_root,
            )
            return 0
        # Fall through into normal print of the now-non-optional step.

    if peek.exhausted or peek.step is None:
        if _emit_run_completed_if_needed(
            plan, events, events_path, run_id,
            slug=slug, projects_root=projects_root,
        ):
            print(render_step_instructions(
                "Run complete. Nothing to do.",
                projects_root=projects_root,
                slug=slug,
                run_id=run_id,
                plan_step_path=None,
                item_id=None,
                iteration=None,
            ))
            # Post-completion handoff (#27 + Fix 3): seq probe found agents
            # had to know to abort + start the next orchestrator manually.
            # Now that current_run.json was just cleared by
            # _emit_run_completed_if_needed, print the start-next hint with
            # a concrete next orchestrator id (not just a placeholder), so
            # the sequential flow reads as one continuous instruction stream.
            _print_post_completion_handoff(
                slug,
                just_finished_plan_id=getattr(plan, "plan_id", None),
            )
        else:
            parked = STEP_PATH_SEP.join(peek.path_tuple) if peek.path_tuple else "<root>"
            print(
                f"run not complete: cursor parked at {parked} with no legal action",
                file=sys.stderr,
            )
        return 0

    path_str = STEP_PATH_SEP.join(peek.path_tuple)

    _render_kwargs = dict(
        projects_root=projects_root,
        slug=slug,
        run_id=run_id,
        plan_step_path=peek.path_tuple,
        item_id=peek.item_id,
        iteration=peek.iteration,
    )

    if is_code_kind(peek.step):
        print(f"run: {render_step_instructions(peek.step.command, **_render_kwargs)}")
        if not _command_has_project_arg(peek.step.command):
            print(
                "warning: this code-step command has no --project argument, so running it "
                "directly will not re-enter the Astrid task gate or advance the run. "
                "Fix the authored plan so the step runs through `python3 -m astrid ... --project "
                f"{slug}`."
            )
        print(
            "(rerun the same command if it failed; the gate detects re-entry "
            "and skips a duplicate step_dispatched event.)"
        )
    elif is_attested_kind(peek.step):
        print(render_step_instructions(
            peek.step.instructions or peek.step.command or "",
            **_render_kwargs,
        ))
        # Polish #29: surface json_schema required keys inline so the
        # instructions and the verifier can't drift (4/4 v3+v6 probes
        # hit this on schema_strict). Emits "required keys for X: a, b, c"
        # per produces entry when the check is json_schema with required
        # fields; silent for non-schema produces.
        schema_reqs = _format_schema_requirements(peek.step)
        if schema_reqs:
            print()
            print(schema_reqs)
        print()
        # peek.step.repeat is None when the leaf is the body of a repeat
        # frame (the body is a clone with repeat stripped) — peek.item_id
        # being set is the reliable signal that we're inside a for_each
        # host. Fall back to looking up the host in the plan when item_id
        # is None to handle a top-level for_each that hasn't dispatched yet.
        host_has_for_each = peek.item_id is not None
        if not host_has_for_each:
            host_step = _find_step_by_path(plan, peek.path_tuple)
            if host_step is not None and isinstance(
                getattr(host_step, "repeat", None), RepeatForEach
            ):
                host_has_for_each = True
        print(
            _format_ack_template(
                path_str=path_str,
                slug=slug,
                ack_kind=(peek.step.ack.kind if peek.step.ack is not None else "agent"),
                has_repeat_for_each=host_has_for_each,
            )
        )
    else:
        # Defensive: peek_current_step should never surface a NestedStep.
        _print_err(f"next: unexpected step kind {type(peek.step).__name__}")
        return 1

    # Iteration ledger: at peek.iteration == N (>=2), read iteration N-1's
    # cumulative feedback.json (written by write_iteration_feedback).
    if peek.iteration is not None and peek.iteration >= 2:
        prev_iter = peek.iteration - 1
        try:
            prev_dir = step_dir_for_path(
                slug,
                run_id,
                peek.path_tuple,
                step_version=1,
                iteration=prev_iter,
                root=projects_root,
            )
        except Exception:
            prev_dir = None
        if prev_dir is not None:
            feedback_path = prev_dir / "feedback.json"
            if feedback_path.is_file():
                try:
                    payload = json.loads(feedback_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = None
                if isinstance(payload, list):
                    print()
                    print(f"feedback ledger (through iteration {prev_iter}):")
                    for idx, entry in enumerate(payload, start=1):
                        print(f"  [{idx}] {entry}")

    # for_each item ledger: when peek.item_id is set, the leaf is the body
    # step inside a for_each frame; peek.path_tuple matches the host path
    # because _make_item_frame uses path_prefix = parent_prefix and the body
    # carries the host's id. Look the host step up directly from the plan
    # (peek does not persist for_each_expanded to events.jsonl, so
    # derive_cursor's for_each_progress would be empty here).
    if peek.item_id is not None:
        host_path = STEP_PATH_SEP.join(peek.path_tuple)
        host_step = _find_step_by_path(plan, peek.path_tuple)
        items: list[str] = []
        host_repeat = getattr(host_step, "repeat", None) if host_step is not None else None
        if isinstance(host_repeat, RepeatForEach):
            host_for_each: RepeatForEach = host_repeat
            if host_for_each.items_source == "static":
                items = list(host_for_each.items)
            # Dynamic items source — items are resolved at gate dispatch from
            # a sibling produces JSON file. peek shares the same resolution
            # path; if events.jsonl has a for_each_expanded event for this
            # host (because dispatch ran earlier) we can recover items from
            # there instead.
        if not items:
            for ev in events:
                if (
                    isinstance(ev, dict)
                    and ev.get("kind") == "for_each_expanded"
                    and ev.get("plan_step_path") == list(peek.path_tuple)
                ):
                    raw = ev.get("item_ids") or []
                    if isinstance(raw, list):
                        items = [str(x) for x in raw]
                    break
        completed = _completed_items_from_events(events, host_path)
        if items:
            print()
            print(f"for_each items (host {host_path}):")
            for item in items:
                marker = "x" if item in completed else " "
                star = "  <- next" if item == peek.item_id else ""
                print(f"  [{marker}] {item}{star}")

    return 0


# ---------------------------------------------------------------------------
# cmd_runs_ls
# ---------------------------------------------------------------------------


def _summarize_run_dir(run_dir: Path) -> tuple[str, str, str]:
    """Return (status, last_event_kind, last_ts) for a run directory.

    Status:
    - ``completed`` — terminal ``run_completed`` event present anywhere
      in the chain (not just the tail; advisory events like a late
      ``takeover`` can land after it).
    - ``aborted`` — terminal ``run_aborted`` event present.
    - ``in-flight`` — neither terminal event seen yet; the run is still
      being driven.

    Fix #26: pre-#26 the check looked only at ``events[-1]`` which missed
    runs where ``run_completed`` was followed by ``takeover`` or other
    advisory tails — `astrid runs ls` showed "in-flight" for runs the
    v4 probes had clearly finished. Now scans the full event list.
    """
    events_path = run_dir / "events.jsonl"
    if not events_path.is_file():
        return "in-flight", "", ""
    events = read_events(events_path)
    if not events:
        return "in-flight", "", ""
    last = events[-1]
    last_kind = str(last.get("kind", ""))
    last_ts = str(last.get("ts", ""))
    # Scan the whole chain for a terminal event; aborted wins over completed
    # if both somehow land (only the most-recent terminal is meaningful).
    terminal_kind: str | None = None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = ev.get("kind")
        if kind in ("run_completed", "run_aborted"):
            terminal_kind = str(kind)
    if terminal_kind == "run_aborted":
        return "aborted", last_kind, last_ts
    if terminal_kind == "run_completed":
        return "completed", last_kind, last_ts
    return "in-flight", last_kind, last_ts


_RUNS_LS_STATUSES = ("completed", "in-flight", "aborted")


def cmd_runs_ls(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid runs ls", add_help=True)
    parser.add_argument("--project", default=None, help="optional project slug filter")
    parser.add_argument(
        "--status",
        default=None,
        choices=_RUNS_LS_STATUSES,
        help="filter by terminal status",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    if args.project is not None:
        try:
            slug = validate_project_slug(args.project)
        except Exception as exc:
            _print_err(f"runs ls: {exc}")
            return 1
        project_dirs = [project_dir(slug, root=projects_root)]
    else:
        root = resolve_projects_root(projects_root)
        if not root.is_dir():
            return 0
        project_dirs = sorted(p for p in root.iterdir() if p.is_dir())

    rows: list[tuple[str, str, str, str, str]] = []
    for proj in project_dirs:
        runs_root = proj / "runs"
        if not runs_root.is_dir():
            continue
        for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            status, last_kind, last_ts = _summarize_run_dir(run_dir)
            if args.status is not None and status != args.status:
                continue
            rows.append((proj.name, run_dir.name, status, last_kind, last_ts))

    for slug, run_id, status, last_kind, last_ts in rows:
        print(f"{slug}\t{run_id}\t{status}\t{last_kind}\t{last_ts}")
    return 0


# ---------------------------------------------------------------------------
# cmd_step_retry_fetch
# ---------------------------------------------------------------------------


def cmd_step_retry_fetch(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Retry artifact fetch for a step in ``awaiting_fetch`` state."""
    from astrid.core.adapter.remote_artifact_fetch import fetch_artifacts
    from astrid.core.task.plan_verbs import apply_mutations
    from astrid.core.task.plan import iter_steps_with_path

    parser = argparse.ArgumentParser(prog="astrid step retry-fetch", add_help=True)
    parser.add_argument("step_id", help="step id (e.g. transcribe, render)")
    parser.add_argument("--run", default=None, dest="run_id", help="run id")
    parser.add_argument("--project", default=None, help="project slug")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    if args.project is not None:
        try:
            slug = validate_project_slug(args.project)
        except Exception as exc:
            _print_err(f"step retry-fetch: {exc}")
            return 1
    else:
        _print_err("step retry-fetch: --project is required")
        return 1

    if args.run_id is not None:
        try:
            run_id = validate_run_id(args.run_id)
        except Exception as exc:
            _print_err(f"step retry-fetch: --run {exc}")
            return 1
    else:
        current = read_current_run(slug, root=projects_root)
        if current is None:
            _print_err(
                f"step retry-fetch: no active run for project {slug!r} "
                f"and --run not specified"
            )
            return 1
        run_id = current

    proj_root = project_dir(slug, root=projects_root)
    run_dir = proj_root / "runs" / run_id
    if not run_dir.is_dir():
        _print_err(
            f"step retry-fetch: run {run_id!r} not found in project {slug!r}"
        )
        return 1

    events_path = run_dir / "events.jsonl"
    if not events_path.is_file():
        _print_err(
            f"step retry-fetch: no events.jsonl for run {run_id!r}"
        )
        return 1

    events = read_events(events_path)
    if not events:
        _print_err(
            f"step retry-fetch: empty events log for run {run_id!r}"
        )
        return 1

    step_id = args.step_id
    latest_event = _latest_event_for_step(events, step_id)
    if latest_event is None:
        _print_err(
            f"step retry-fetch: no events found for step {step_id!r} "
            f"in run {run_id!r}"
        )
        return 1

    latest_kind = latest_event.get("kind")

    if latest_kind == "step_completed":
        _print_err(
            f"step retry-fetch: step {step_id!r} is already completed"
        )
        return 0

    if latest_kind == "step_failed":
        _print_err(
            f"step retry-fetch: step {step_id!r} is failed, not awaiting_fetch"
        )
        return 1

    if latest_kind != "step_awaiting_fetch":
        _print_err(
            f"step retry-fetch: step {step_id!r} is in state "
            f"{latest_kind!r}, expected awaiting_fetch"
        )
        return 1

    plan_path = proj_root / "plan.json"
    if not plan_path.is_file():
        _print_err(
            f"step retry-fetch: plan.json not found for project {slug!r}"
        )
        return 1

    plan = load_plan(plan_path)
    effective = apply_mutations(plan, events)

    target_step: Step | None = None
    target_path: tuple[str, ...] = ()
    for path_tuple, s in iter_steps_with_path(effective):
        if s.id == step_id and target_step is None:
            target_step = s
            target_path = path_tuple

    if target_step is None:
        _print_err(
            f"step retry-fetch: step {step_id!r} not found in effective plan"
        )
        return 1

    step_version = target_step.version

    from astrid.core.adapter import RunContext

    run_ctx = RunContext(
        slug=slug,
        run_id=run_id,
        project_root=proj_root,
        plan_step_path=target_path,
        step_version=step_version,
    )

    fetch_result = fetch_artifacts(target_step, run_ctx)

    if fetch_result.status == "completed":
        path_str = STEP_PATH_SEP.join(target_path)
        with writer_context_for_project(slug, root=projects_root) as writer:
            writer.append(
                make_step_completed_event(
                    path_str,
                    0,
                    adapter="remote-artifact",
                )
            )
        print(f"step {step_id}: all artifacts fetched")

        events_after = read_events(events_path)
        plan_after = load_plan(plan_path)
        if _run_is_complete(plan_after, events_after):
            with writer_context_for_project(slug, root=projects_root) as writer:
                writer.append(make_run_completed_event(run_id))
            print(f"run {run_id}: completed")
        return 0

    if fetch_result.status == "awaiting_fetch":
        path_str = STEP_PATH_SEP.join(target_path)
        with writer_context_for_project(slug, root=projects_root) as writer:
            writer.append(
                make_step_awaiting_fetch_event(
                    path_str,
                    missing=list(fetch_result.missing),
                    mismatched=list(fetch_result.mismatched),
                    reason=fetch_result.reason,
                    adapter="remote-artifact",
                )
            )
        _print_err(
            f"step {step_id}: still awaiting_fetch: "
            f"missing={fetch_result.missing}, mismatched={fetch_result.mismatched}"
        )
        return 1

    _print_err(f"step retry-fetch: fetch failed: {fetch_result.reason}")
    return 1


def _latest_event_for_step(
    events: list[dict[str, Any]],
    step_id: str,
) -> dict[str, Any] | None:
    """Return the latest event whose leaf step id matches *step_id*."""
    latest: dict[str, Any] | None = None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        path_list = ev.get("plan_step_path")
        if isinstance(path_list, list) and path_list and path_list[-1] == step_id:
            latest = ev
    return latest


from astrid.core.task.lifecycle_ack import cmd_ack  # noqa: E402
from astrid.core.task.lifecycle_skip import cmd_skip  # noqa: E402

__all__ = [
    "cmd_abort",
    "cmd_ack",
    "cmd_next",
    "cmd_runs_ls",
    "cmd_skip",
    "cmd_start",
    "cmd_status",
    "cmd_step_retry_fetch",
]
