"""``astrid ack`` lifecycle verb (Phase 5 T9).

Split out of ``lifecycle.py`` to keep both modules under the ~600-line size
budget. Implements the ack decision matrix per the Phase 5 brief:

- ``approve`` (attested cursor): synthesizes the gate-bound incoming command
  as ``step.command + identity/evidence/item tokens`` (NOT ``ack --step ...``)
  so ``match_attested_command`` can strip identity tokens and compare the
  literal remainder to ``step.command`` for authored commands like
  ``review.sh``. Calls ``gate_command`` + ``record_dispatch_complete``.
  (FLAG-P5-001.)
- ``approve`` on an automatically completing leaf cursor: rejected. Those steps advance via the
  printed argv, not via ``ack``.
- ``retry``: only valid on an attested leaf cursor whose latest event for
  the path is ``produces_check_failed``. Calls ``validate_attested_identity``
  BEFORE mutating events, then appends ``cursor_rewind`` so the next
  ``next`` re-dispatches. (FLAG-P5-002.)
- ``iterate``: legacy compatibility for attested leaf cursors whose migrated
  host still has ``repeat.until.condition == 'user_approves'``. New v2
  expression repeats are driven by produced JSON and do not use this branch.
  Requires non-empty ``--feedback``. Calls ``validate_attested_identity``
  BEFORE mutating events, then ``write_iteration_feedback`` (cumulative
  ledger) and appends ``iteration_failed`` so the next ``next`` enters
  iteration N+1. (FLAG-P5-002.)
- ``abort``: administrative — delegates to ``cmd_abort`` and skips identity
  validation entirely.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import Optional, Sequence

from astrid.core.contracts.errors import AstridError
from astrid.core.session.current_run_state import read_current_run_state
from astrid.core.foundation.project_paths import project_dir, validate_project_slug
from astrid.core.session.writer import NoRunBoundError, writer_context_for_project
from astrid.core.task.cli_contract import emit_lifecycle_json, exit_with_astrid_error
from astrid.core.task.events import (
    EventLogError,
    make_cursor_rewind_event,
    make_iteration_failed_event,
    read_events,
)
from astrid.core.task.gate import (
    AttestedArgs,
    GateDecision,
    TaskRunGateError,
    gate_command,
    peek_current_step,
    record_dispatch_complete,
    validate_attested_identity,
    write_iteration_feedback,
)
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatUntil,
    find_step_by_path,
    is_attested_kind,
    is_code_kind,
    is_legacy_repeat_until_condition,
    load_plan,
    step_dir_for_path,
)


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _system_exit_code(exc: SystemExit) -> int:
    return int(exc.code) if isinstance(exc.code, int) else 2


def _exit_recoverable(cause: str, *, recovery: str = "", **snapshot: object) -> int:
    """Exit with a recoverable validation failure via the shared error envelope."""
    return exit_with_astrid_error(
        AstridError(
            cause,
            recovery_command=recovery,
            state_snapshot=snapshot if snapshot else None,
        )
    )


def _latest_event_for_path(events, path_tuple, *, step_version: int | None = None):
    path_str = STEP_PATH_SEP.join(path_tuple)
    path_list = list(path_tuple)
    for ev in reversed(events):
        if not isinstance(ev, dict):
            continue
        if step_version is not None:
            raw_version = ev.get("step_version", 1)
            if not isinstance(raw_version, int) or isinstance(raw_version, bool) or raw_version != step_version:
                continue
        if ev.get("plan_step_id") == path_str:
            return ev
        if ev.get("plan_step_path") == path_list:
            return ev
    return None


def _run_started_actor(events) -> Optional[str]:
    for ev in events:
        if isinstance(ev, dict) and ev.get("kind") == "run_started":
            started_by = ev.get("started_by")
            if isinstance(started_by, str) and started_by.startswith("human:"):
                return started_by[len("human:"):]
            # Legacy read compatibility for pre-T5 run_started events.
            actor = ev.get("actor")
            return actor if isinstance(actor, str) else None
    return None


def cmd_ack(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    # --- Early abort decision: handle before argparse so identity flags are not required ---
    argv_list = list(argv)
    abort_idx = None
    for i, a in enumerate(argv_list):
        if a == "--decision" and i + 1 < len(argv_list) and argv_list[i + 1] == "abort":
            abort_idx = i
            break
    if abort_idx is not None:
        # Extract --project for cmd_abort.
        proj = None
        for i, a in enumerate(argv_list):
            if a == "--project" and i + 1 < len(argv_list):
                proj = argv_list[i + 1]
                break
        if proj is None:
            _print_err("ack: --project is required for abort")
            return 1
        # Forward --json when present so abort can emit structured output.
        has_json = "--json" in argv_list
        from astrid.core.task.run.store import cmd_abort
        abort_argv = ["--project", proj]
        if has_json:
            abort_argv.append("--json")
        return cmd_abort(abort_argv, projects_root=projects_root)

    parser = argparse.ArgumentParser(prog="astrid ack", add_help=True)
    parser.add_argument("step", help="STEP_PATH_SEP-joined plan step path (e.g. 'review' or 'outer/inner')")
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument(
        "--decision",
        required=True,
        choices=["approve", "retry", "iterate", "abort"],
        help="ack decision",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="repeatable; evidence path or sentinel",
    )
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--agent", default=None, help="agent id (mutually exclusive with --human)")
    identity.add_argument("--human", default=None, help="human name (mutually exclusive with --agent)")
    parser.add_argument("--feedback", default=None, help="iterate feedback (required for --decision=iterate)")
    parser.add_argument("--item", default=None, help="for_each item id")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit exactly one machine-readable ack object on stdout",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    # --- Function-boundary identity assertion (Sprint 3 T16) ---
    # argparse `required=True` catches the CLI case. This assertion catches
    # Python callers that synthesize Namespace(agent=None, human=None) directly.
    if args.agent is None and args.human is None:
        return _exit_recoverable(
            "ack: --agent <id> or --human <name> is required "
            "(no anonymous acks — Sprint 3 T16)"
        )

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        return _exit_recoverable(f"ack: {exc}")

    active_run = read_current_run_state(slug, root=projects_root)
    if active_run is None:
        return _exit_recoverable(
            f"ack: no active run for project {slug!r}",
            recovery=f"astrid start <orchestrator-id> --project {slug}",
        )

    run_id = active_run["run_id"]
    proj_root = project_dir(slug, root=projects_root)
    plan_path = proj_root / "plan.json"
    events_path = proj_root / "runs" / run_id / "events.jsonl"

    plan = load_plan(plan_path)
    events = read_events(events_path)
    peek = peek_current_step(
        plan, events, slug, project_root=proj_root, run_id=run_id
    )
    if peek.exhausted or peek.step is None:
        return _exit_recoverable(
            f"ack: run is exhausted",
            recovery=f"astrid abort --project {slug}",
        )

    expected_path = STEP_PATH_SEP.join(peek.path_tuple)
    if args.step != expected_path:
        return _exit_recoverable(
            f"ack: step path {args.step!r} does not match cursor {expected_path!r}",
            recovery=f"astrid next --project {slug}",
        )

    try:
        if args.decision == "approve":
            return _ack_approve(args, slug, peek, projects_root, proj_root)
        if args.decision == "retry":
            return _ack_retry(
                args, slug, peek, plan, events, events_path, run_id, proj_root
            )
        if args.decision == "iterate":
            return _ack_iterate(
                args, slug, peek, plan, events, events_path, run_id, proj_root
            )
    except Exception as exc:
        from astrid.core.task.events import StaleEpochError, StaleTailError
        if isinstance(exc, (StaleEpochError, StaleTailError)):
            return _exit_recoverable(
                f"ack: stale — {exc}; the run lease has changed under you. "
                f"Re-run the ack to pick up the new writer_epoch."
            )
        raise
    # argparse choices=... already constrains this; defensive only.
    return _exit_recoverable(f"ack: unknown decision {args.decision!r}")


def _ack_approve(args, slug, peek, projects_root, proj_root) -> int:
    json_mode = bool(getattr(args, "json", False))
    if is_code_kind(peek.step):
        return _exit_recoverable(
            "ack: approve is invalid for code steps. code steps advance via "
            f"subprocess; just run the printed command (astrid next --project {slug})."
        )
    if not is_attested_kind(peek.step):
        return _exit_recoverable("ack: cannot approve non-attested step")

    # FLAG-P5-001: synthesize the incoming command as step.command +
    # identity/evidence/item tokens, NOT 'ack --step ...'. step.command may
    # already be a multi-token command (e.g., "echo review"); split it so
    # match_attested_command's canonical rejoin compares token-for-token
    # rather than treating the whole prefix as a single quoted argument.
    parts: list[str] = shlex.split(peek.step.command)
    if args.agent:
        parts += ["--agent", args.agent]
    if args.human:
        parts += ["--human", args.human]
    for ev in args.evidence:
        parts += ["--evidence", ev]
    if args.item:
        parts += ["--item", args.item]
    incoming = " ".join(shlex.quote(p) for p in parts)

    try:
        decision = gate_command(slug, incoming, [], root=projects_root)
    except TaskRunGateError as exc:
        return _exit_recoverable(
            f"ack: {exc.reason}", recovery=exc.recovery
        )

    # Attested step is "complete" at attestation; the gate already wrote
    # step_attested + ran inline produces checks. record_dispatch_complete
    # is a no-op for attested steps but we call it for symmetry with code
    # dispatch and to keep the post-dispatch surface consistent.
    record_dispatch_complete(decision, 0)

    # FLAG-S1-005: surface inline produces-check rejection through cmd_ack's
    # exit code (2 = inline-check rejected, distinct from generic 1) and
    # print the rejection reason to stderr. The decision field is populated
    # ONLY in gate._dispatch_attested (never in record_dispatch_complete), so
    # code-step rewinds never reach this branch by design.
    if decision.inline_check_result is not None:
        from astrid.core.task.operator.view import render_step_instructions
        name, reason = decision.inline_check_result
        decision_run_id = decision.run_id or ""
        produces_entry = next(
            (p for p in peek.step.produces if p.name == name),
            None,
        )
        if produces_entry is not None and decision_run_id:
            step_dir = step_dir_for_path(
                slug,
                decision_run_id,
                peek.path_tuple,
                step_version=peek.step.version,
                iteration=peek.iteration,
                item_id=peek.item_id,
                root=projects_root,
            )
            artifact_path = step_dir / "produces" / produces_entry.path
        else:
            artifact_path = Path("<unknown>")
        msg = render_step_instructions(
            f"ack accepted, but produces check failed for {name}: {reason}. "
            f"Retry: re-write {artifact_path} and re-ack.",
            projects_root=projects_root,
            slug=slug,
            run_id=decision_run_id,
            plan_step_path=peek.path_tuple,
            item_id=peek.item_id,
            iteration=peek.iteration,
        )
        _print_err(msg)
        return 2

    step_path = STEP_PATH_SEP.join(peek.path_tuple)
    if json_mode:
        return emit_lifecycle_json(
            project=slug,
            run_id=decision.run_id or "",
            state="acknowledged",
            step_path=step_path,
            decision="approve",
        )
    print(f"acknowledged {step_path}")
    return 0


def _ack_retry(args, slug, peek, plan, events, events_path, run_id, proj_root) -> int:
    json_mode = bool(getattr(args, "json", False))
    if not is_attested_kind(peek.step):
        return _exit_recoverable(
            "ack: retry is only valid on attested steps. Code steps "
            "redispatch implicitly when you re-run the printed argv."
        )

    # FLAG-P5-002: validate identity BEFORE mutating events.
    attested_args = AttestedArgs(
        agent=args.agent,
        human=args.human,
        evidence=tuple(args.evidence),
        item=args.item,
    )
    try:
        validate_attested_identity(
            slug=slug,
            step=peek.step,
            args=attested_args,
            run_started_actor=_run_started_actor(events),
        )
    except TaskRunGateError as exc:
        return _exit_recoverable(
            f"ack retry: {exc.reason}", recovery=exc.recovery
        )

    latest = _latest_event_for_path(events, peek.path_tuple, step_version=peek.step.version)
    if not isinstance(latest, dict) or latest.get("kind") != "produces_check_failed":
        return _exit_recoverable(
            "ack retry: only valid after a verifier failure (the latest event "
            f"for {STEP_PATH_SEP.join(peek.path_tuple)} must be "
            "produces_check_failed)."
        )

    try:
        with writer_context_for_project(slug, root=proj_root.parent) as writer:
            writer.append(
                make_cursor_rewind_event(
                    peek.path_tuple,
                    reason="ack retry",
                    step_version=peek.step.version,
                    dispatch_event_hash=latest.get("dispatch_event_hash")
                    if isinstance(latest.get("dispatch_event_hash"), str)
                    else None,
                )
            )
    except (EventLogError, NoRunBoundError, RuntimeError) as exc:
        _print_err(f"ack retry: event append failed: {exc}")
        return 1
    step_path = STEP_PATH_SEP.join(peek.path_tuple)
    if json_mode:
        return emit_lifecycle_json(
            project=slug,
            run_id=run_id,
            state="retry_queued",
            step_path=step_path,
            decision="retry",
        )
    print(f"retry queued for {step_path}")
    return 0


def _ack_iterate(args, slug, peek, plan, events, events_path, run_id, proj_root) -> int:
    json_mode = bool(getattr(args, "json", False))
    if not is_attested_kind(peek.step):
        return _exit_recoverable("ack: iterate is only valid on attested steps")
    if not args.feedback or not args.feedback.strip():
        return _exit_recoverable("ack iterate: --feedback is required and must be non-empty")

    # FLAG-P5-002: validate identity BEFORE mutating events.
    attested_args = AttestedArgs(
        agent=args.agent,
        human=args.human,
        evidence=tuple(args.evidence),
        item=args.item,
    )
    try:
        validate_attested_identity(
            slug=slug,
            step=peek.step,
            args=attested_args,
            run_started_actor=_run_started_actor(events),
        )
    except TaskRunGateError as exc:
        return _exit_recoverable(
            f"ack iterate: {exc.reason}", recovery=exc.recovery
        )

    # Find the host step in the plan (peek.step has repeat stripped because
    # it is the body of an iteration frame). peek.path_tuple == host path
    # because _make_iteration_frame uses path_prefix = parent_prefix.
    host = find_step_by_path(plan, peek.path_tuple)
    host_repeat = getattr(host, "repeat", None) if host is not None else None
    if (
        host is None
        or not isinstance(host_repeat, RepeatUntil)
        or not is_legacy_repeat_until_condition(host_repeat.condition)
        or host_repeat.condition != "user_approves"
    ):
        condition = (
            host_repeat.condition
            if isinstance(host_repeat, RepeatUntil)
            else "<no repeat>"
        )
        return _exit_recoverable(
            "ack iterate: only valid for legacy repeat.until.condition='user_approves' "
            f"(host condition={condition!r})"
        )
    if peek.iteration is None:
        return _exit_recoverable("ack iterate: cursor is not inside an iteration frame")

    decision = GateDecision(
        active=True,
        run_id=run_id,
        slug=slug,
        project_root=proj_root,
        plan_step_path=peek.path_tuple,
        iteration=peek.iteration,
        events_path=events_path,
        step_version=peek.step.version,
    )
    write_iteration_feedback(decision, args.feedback)
    try:
        with writer_context_for_project(slug, root=proj_root.parent) as writer:
            writer.append(
                make_iteration_failed_event(
                    peek.path_tuple,
                    peek.iteration,
                    reason="iterate_feedback",
                    step_version=peek.step.version,
                )
            )
    except (EventLogError, NoRunBoundError, RuntimeError) as exc:
        _print_err(f"ack iterate: event append failed: {exc}")
        return 1
    step_path = STEP_PATH_SEP.join(peek.path_tuple)
    if json_mode:
        return emit_lifecycle_json(
            project=slug,
            run_id=run_id,
            state="iteration_failed",
            step_path=step_path,
            decision="iterate",
            iteration=peek.iteration,
            feedback=args.feedback.strip(),
        )
    print(
        f"iteration {peek.iteration} marked failed; feedback recorded for "
        f"{step_path}"
    )
    return 0


__all__ = ["cmd_ack"]
