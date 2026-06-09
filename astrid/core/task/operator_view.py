"""Phase 5 lifecycle verbs: start/abort/status/runs ls/next; cmd_ack lives
in lifecycle_ack.py to keep both modules under the size budget.

cmd_runs_ls (FLAG-P5-006): natural completion does not clear active_run.json
in V1, so the lister surfaces only 'aborted' vs 'in-progress'.
cmd_start (SD-007): does not silently invoke compile when the pre-built JSON
manifest is missing — prints the compile recovery and returns non-zero.
Author-test replays are the exception: they deliberately use compiled smoke
plans even for orchestrators that normally build dynamic start plans.

Implementation split (M4 T58 / T60):
- ``operator_render.py``: human-readable rendering, audit helpers, tail-dispatch,
  ack templates, and post-completion handoff.
- ``operator_view.py`` (this module): command adapters ``cmd_status`` and
  ``cmd_next``, inline-failure helpers, ``cmd_status --json`` payload,
  plus backward-compatibility re-exports from operator_render.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from astrid.core.contracts.run_status import RunStatus, STEP_TERMINAL_KINDS
from astrid.core.project.current_run import (
    read_current_run_state,
)
from astrid.core.foundation.project_paths import (
    project_dir,
    resolve_projects_root,
    validate_project_slug,
)
from astrid.core.session.writer import writer_context_for_project
from astrid.core.task.claim import active_claims_by_step
from astrid.core.task.cli_contract import emit_lifecycle_json
from astrid.core.task.command_render import render_task_command
from astrid.core.task.events import (
    EventLogError,
    read_events,
)
from astrid.core.task.gate import TaskRunGateError, peek_current_step
from astrid.core.task.inbox import consume_inbox_entry, pending_count, scan_inbox
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    find_step_by_path,
    is_attested_kind,
    is_code_kind,
    is_group_step,
    is_leaf_step,
    iter_steps_with_path,
    load_plan,
    step_dir_for_path,
)
from astrid.core.task.plan_verbs import apply_mutations
from astrid.core.task.preamble import PROHIBITION_PREAMBLE
from astrid.core.task.run_state import _run_is_complete
from astrid.core.task.run_store import _emit_run_completed_if_needed
from astrid.core.session.discovery_hints import (
    _most_recent_session_slug,
    _os_environ_has_session,
    _print_next_no_run_hint,
    _print_next_unbound_hint,
)

# -- Status JSON helpers ----------------------------------------------------
from astrid.core.task.inbox import pending_count as _pending_count


def _status_json(
    *,
    slug: str,
    run_id: str,
    plan,
    events: Sequence[dict],
    peek,
    claims: dict[str, str],
    completed: int,
    total: int,
    proj_root: Path,
) -> int:
    """Emit the ``cmd_status --json`` payload via the shared lifecycle helper."""
    run_state = RunStatus.from_run_events(events).value
    payload: dict[str, Any] = {
        "progress_completed": completed,
        "progress_total": total,
        "current_step": None,
        "current_step_kind": None,
        "current_step_version": None,
        "current_step_iteration": None,
        "current_step_item_id": None,
        "inbox_pending": _pending_count(proj_root / "runs" / run_id),
    }
    if not (peek.exhausted or peek.step is None):
        path_str = STEP_PATH_SEP.join(peek.path_tuple)
        payload["current_step"] = path_str
        payload["current_step_kind"] = (
            "nested" if is_group_step(peek.step)
            else "attested" if is_attested_kind(peek.step)
            else "code"
        )
        payload["current_step_version"] = peek.step.version
        payload["current_step_iteration"] = peek.iteration
        payload["current_step_item_id"] = peek.item_id
        claimed_identity = claims.get(path_str)
        if peek.step.assignee != "system" or claimed_identity is not None:
            payload["owner_assignee"] = getattr(peek.step, "assignee", "system")
            payload["owner_claimed"] = claimed_identity

    inline_failure = _inline_failure_tail(events)
    if inline_failure is not None:
        payload["blocked_reason"] = f"produces check failed: {_format_inline_failure_tail(inline_failure)}"
        payload["blocked_step"] = STEP_PATH_SEP.join(inline_failure.path) if inline_failure.path else None
    elif events and isinstance(events[-1], dict) and events[-1].get("kind") in {"cursor_rewind", "iteration_failed"}:
        reason = events[-1].get("reason")
        if reason:
            payload["blocked_reason"] = reason
            blocked_path = _path_tuple_from_event(events[-1])
            payload["blocked_step"] = STEP_PATH_SEP.join(blocked_path) if blocked_path else None

    return emit_lifecycle_json(
        project=slug,
        run_id=run_id,
        state=run_state,
        **payload,
    )


# ── Re-exports from operator_render.py for backward compatibility ──────────
# These names must remain accessible as astrid.core.task.operator_view.<name>
# because lifecycle.py, lifecycle_ack.py, and test monkeypatch seams reference
# them through this module.
from astrid.core.task.operator_render import (  # noqa: E402, F401
    _AckTemplate,
    _ack_identity_token,
    _ack_template_parts,
    _command_has_project_arg,
    _completed_items_from_events,
    _default_projects_root,
    _dispatch_from_tail,
    _emit_for_each_autoclose_audit,
    _expected_for_each_total,
    _format_ack_template,
    _format_claim_line,
    _format_inline_failure_tail,
    _format_schema_requirements,
    _has_host_step_attested,
    _HostCloseHint,
    _identity_parts,
    _InlineFailureTail,
    _inline_failure_tail,
    _leaf_progress,
    _path_tuple_from_event,
    _print_post_completion_handoff,
    _PROGRESS_TERMINAL_KINDS,
    _RewindRetry,
    _RunComplete,
    NEXT_JSON_SCHEMA,
    render_step_instructions,
)
__all__ = [
    "cmd_next",
    "cmd_status",
    "NEXT_JSON_SCHEMA",
    "render_step_instructions",
]


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _system_exit_code(exc: SystemExit) -> int:
    return int(exc.code) if isinstance(exc.code, int) else 2


def cmd_status(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid status", add_help=True)
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit exactly one machine-readable status object on stdout",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        _print_err(f"status: {exc}")
        return 1

    json_mode = bool(args.json)

    active_run = read_current_run_state(slug, root=projects_root)
    if active_run is None:
        msg = (
            f"status: no active run for project {slug!r}; "
            f"recovery: astrid start <orchestrator-id> --project {slug}"
        )
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=None,
                state="no_active_run",
                error=msg,
            )
        _print_err(msg)
        return 1

    run_id = active_run["run_id"]
    plan_hash = active_run["plan_hash"]
    proj_root = project_dir(slug, root=projects_root)
    plan_path = proj_root / "plan.json"
    events_path = proj_root / "runs" / run_id / "events.jsonl"

    events = read_events(events_path)
    plan = apply_mutations(load_plan(plan_path), events)
    claims = active_claims_by_step(events)
    peek = peek_current_step(
        plan, events, slug, project_root=proj_root, run_id=run_id
    )

    completed, total = _leaf_progress(plan, events)

    if json_mode:
        return _status_json(
            slug=slug,
            run_id=run_id,
            plan=plan,
            events=events,
            peek=peek,
            claims=claims,
            completed=completed,
            total=total,
            proj_root=proj_root,
        )

    # ---- default human-readable stdout path ----
    print(f"run-id:    {run_id}")
    print(f"plan-hash: {plan_hash}")
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
        claimed_identity = claims.get(path_str)
        if peek.step.assignee != "system" or claimed_identity is not None:
            print(f"owner:     {_format_claim_line(step=peek.step, claimed_identity=claimed_identity)}")

    pending = pending_count(proj_root / "runs" / run_id)
    if pending > 0:
        print(f"inbox:     {pending} pending")

    # Diagnostics: produces-check failures and cursor-rewind errors go to stderr
    inline_failure = _inline_failure_tail(events)
    if inline_failure is not None:
        path_str = STEP_PATH_SEP.join(inline_failure.path)
        print(
            f"{RunStatus.BLOCKED.value}:   produces check failed"
            f"{f' for {path_str}' if path_str else ''}: "
            f"{_format_inline_failure_tail(inline_failure)}",
            file=sys.stderr,
        )
    elif events and isinstance(events[-1], dict) and events[-1].get("kind") in {"cursor_rewind", "iteration_failed"}:
        reason = events[-1].get("reason")
        if reason:
            path_str = STEP_PATH_SEP.join(_path_tuple_from_event(events[-1]))
            print(
                f"{RunStatus.BLOCKED.value}:   {f'{path_str}: ' if path_str else ''}{reason}",
                file=sys.stderr,
            )

    print("recent events:")
    for ev in events[-5:]:
        kind = ev.get("kind", "?")
        ts = ev.get("ts", "")
        plan_step_id = ev.get("plan_step_id")
        if not isinstance(plan_step_id, str):
            path_tuple = _path_tuple_from_event(ev)
            plan_step_id = "/".join(path_tuple) if path_tuple else ""
        print(f"  {ts}  {kind}  {plan_step_id}")
    return 0


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
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit exactly one machine-readable next-action object on stdout",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the prohibition preamble and separator; keep actionable prose",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    json_mode = bool(args.json)
    if not json_mode and not args.quiet:
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
        if json_mode:
            command = f"astrid attach {slug}" if slug and explicit_project else "astrid status"
            return emit_lifecycle_json(
                project=slug if explicit_project else None,
                run_id=None,
                state="unbound",
                action="attach" if slug and explicit_project else "none",
                command=command,
                step=None,
                blocked=False,
                reason="no session bound",
            )
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
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=None,
                state="no_active_run",
                action="start",
                command=f"astrid start <orchestrator-id> --project {slug}",
                step=None,
                blocked=False,
                reason="session bound but no active task run",
            )
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
        )
        from astrid.core.session.binding import (
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
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=run_id,
                state="reader",
                action="claim",
                command=f"astrid sessions takeover {run_id}",
                step=None,
                blocked=True,
                reason="attached as reader; another session holds the writer lease",
            )
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

    events = read_events(events_path)
    plan = apply_mutations(load_plan(plan_path), events)
    claims = active_claims_by_step(events)
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
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=run_id,
                state="blocked",
                action="ack",
                command=None,
                step=path_str or None,
                blocked=True,
                reason=f"previous attempt rejected: {tail_action.reason}",
            )
        msg = (
            f"Previous attempt rejected: {tail_action.reason}. "
            f"Re-write the artifact for {path_str!r} and re-ack."
        )
        print(render_step_instructions(msg, **{**_tail_render_kwargs, "plan_step_path": tail_action.path or None}))
        return 0
    if isinstance(tail_action, _HostCloseHint):
        host_path_str = STEP_PATH_SEP.join(tail_action.host_path)
        command = (
            f"astrid ack {host_path_str} --project {slug} --decision approve "
            f"--agent <id> --evidence ..."
        )
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=run_id,
                state="ready",
                action="ack",
                command=command,
                step=host_path_str,
                blocked=False,
                reason="all for_each items complete; close the host step",
            )
        msg = (
            f"All items complete. Close the host with `{command}` (omit --item)."
        )
        print(render_step_instructions(
            msg,
            **{**_tail_render_kwargs, "plan_step_path": tail_action.host_path, "item_id": None, "iteration": None},
        ))
        return 0
    if isinstance(tail_action, _RunComplete):
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=run_id,
                state="complete",
                action="none",
                command=None,
                step=None,
                blocked=False,
                reason="run complete",
            )
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
            if not json_mode:
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
            if json_mode:
                return emit_lifecycle_json(
                    project=slug,
                    run_id=run_id,
                    state="complete",
                    action="none",
                    command=None,
                    step=None,
                    blocked=False,
                    reason="run complete (all optional steps skipped)",
                )
            return 0
        # Fall through into normal print of the now-non-optional step.

    if peek.exhausted or peek.step is None:
        if _emit_run_completed_if_needed(
            plan, events, events_path, run_id,
            slug=slug, projects_root=projects_root,
        ):
            if json_mode:
                return emit_lifecycle_json(
                    project=slug,
                    run_id=run_id,
                    state="complete",
                    action="none",
                    command=None,
                    step=None,
                    blocked=False,
                    reason="run complete",
                )
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
            if json_mode:
                parked = STEP_PATH_SEP.join(peek.path_tuple) if peek.path_tuple else "<root>"
                return emit_lifecycle_json(
                    project=slug,
                    run_id=run_id,
                    state="blocked",
                    action="none",
                    command=None,
                    step=parked,
                    blocked=True,
                    reason="cursor parked with no legal action",
                )
            parked = STEP_PATH_SEP.join(peek.path_tuple) if peek.path_tuple else "<root>"
            print(
                f"run not complete: cursor parked at {parked} with no legal action",
                file=sys.stderr,
            )
        return 0

    path_str = STEP_PATH_SEP.join(peek.path_tuple)
    claimed_identity = claims.get(path_str)

    _render_kwargs = dict(
        projects_root=projects_root,
        slug=slug,
        run_id=run_id,
        plan_step_path=peek.path_tuple,
        item_id=peek.item_id,
        iteration=peek.iteration,
    )

    if not json_mode and (peek.step.assignee != "system" or claimed_identity is not None):
        print(_format_claim_line(step=peek.step, claimed_identity=claimed_identity))
        print()

    if is_code_kind(peek.step):
        rendered = render_task_command(
            peek.step,
            slug=slug,
            run_id=run_id,
            project_root=proj_root,
            plan_step_path=peek.path_tuple,
            iteration=peek.iteration,
            item_id=peek.item_id,
        )
        command = render_step_instructions(rendered.display_command, **_render_kwargs)
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=run_id,
                state="ready",
                action="run",
                command=command,
                step=path_str,
                blocked=False,
                reason=None,
            )
        print(f"run: {command}")
        if not _command_has_project_arg(rendered.canonical_command):
            print(
                "warning: this code-step command uses task env instead of a local --project "
                "argument. The printed env-prefixed command is the copy/paste re-entry "
                "form for a normal shell; adapters execute the canonical command under "
                "the same task env."
            )
        print(
            "(rerun the same command if it failed; the gate detects re-entry "
            "and skips a duplicate step_dispatched event.)"
        )
    elif is_attested_kind(peek.step):
        schema_reqs = _format_schema_requirements(peek.step)
        host_has_for_each = peek.item_id is not None
        if not host_has_for_each:
            host_step = find_step_by_path(plan, peek.path_tuple)
            if host_step is not None and isinstance(
                getattr(host_step, "repeat", None), RepeatForEach
            ):
                host_has_for_each = True
        ack_template = _ack_template_parts(
            path_str=path_str,
            slug=slug,
            step=peek.step,
            claimed_identity=claimed_identity,
            has_repeat_for_each=host_has_for_each,
        )
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=run_id,
                state="ready",
                action="ack",
                command=ack_template.command,
                step=path_str,
                blocked=False,
                reason=None,
            )
        print(render_step_instructions(
            peek.step.instructions or peek.step.command or "",
            **_render_kwargs,
        ))
        # Polish #29: surface json_schema required keys inline so the
        # instructions and the verifier can't drift (4/4 v3+v6 probes
        # hit this on schema_strict). Emits "required keys for X: a, b, c"
        # per produces entry when the check is json_schema with required
        # fields; silent for non-schema produces.
        if schema_reqs:
            print()
            print(schema_reqs)
        print()
        # peek.step.repeat is None when the leaf is the body of a repeat
        # frame (the body is a clone with repeat stripped) — peek.item_id
        # being set is the reliable signal that we're inside a for_each
        # host. Fall back to looking up the host in the plan when item_id
        # is None to handle a top-level for_each that hasn't dispatched yet.
        print(ack_template.command)
    else:
        # Defensive: peek_current_step should never surface a group step.
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
                step_version=peek.step.version,
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
        host_step = find_step_by_path(plan, peek.path_tuple)
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
