"""``astrid skip`` lifecycle verb (Sprint 5b: optional steps).

Skips an ``optional=True`` step (leaf or group) at the current cursor
frontier without dispatching its command. Emits ``step_skipped`` (or
``item_skipped`` if ``--item`` is set) under the writer-epoch + tail-hash
CAS, mirroring the locking pattern used by ``cmd_ack``.

Refuses to skip arbitrary future steps — the target path must match the
top-of-cursor's pending step. For group steps with ``optional=True`` the
skip is operative on the un-traversed cursor (no ``nested_entered``); the
cursor advances past the whole subtree on the next replay.

``--json`` emits a single JSON object with shared lifecycle fields plus
``step_path``, ``kind`` (step_skipped or item_skipped), ``actor_kind``,
``actor_id``, ``reason`` (when given), and ``next_command``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from astrid.core.contracts.errors import AstridError
from astrid.core.project.current_run import read_current_run_state
from astrid.core.foundation.project_paths import project_dir, validate_project_slug
from astrid.core.session.writer import writer_context_for_project
from astrid.core.task.cli_contract import emit_lifecycle_json, exit_with_astrid_error
from astrid.core.task.events import (
    EventLogError,
    StaleEpochError,
    StaleTailError,
    make_item_skipped_event,
    make_step_skipped_event,
    read_events,
)
from astrid.core.task.gate import derive_cursor
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    load_plan,
)


def _exit_recoverable(cause: str, *, recovery: str = "", **snapshot: object) -> int:
    """Exit with a recoverable validation failure via the shared error envelope."""
    return exit_with_astrid_error(
        AstridError(
            cause,
            recovery_command=recovery,
            state_snapshot=snapshot if snapshot else None,
        )
    )


def _resolve_frontier_step(plan, events):
    """Return ``(step, path_tuple)`` for the top-of-cursor pending step.

    Uses ``derive_cursor`` (NOT ``peek_current_step``) so group steps are
    surfaced un-traversed — a group step with ``optional=True`` is
    skippable as a single unit before any ``nested_entered`` fires.
    Returns ``(None, ())`` when the cursor is exhausted.
    """
    cursor = derive_cursor(plan, events)
    if cursor.pinned_failure is not None or cursor.at_root_done:
        return None, ()
    top = cursor.frames[-1]
    if top.child_index >= len(top.plan.steps):
        return None, ()
    step = top.plan.steps[top.child_index]
    path_tuple = top.path_prefix + (step.id,)
    return step, path_tuple


def cmd_skip(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid skip", add_help=True)
    parser.add_argument(
        "step",
        help="STEP_PATH_SEP-joined plan step path of the optional step to skip",
    )
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument(
        "--reason",
        default=None,
        help="optional human-readable reason recorded on the skip event",
    )
    parser.add_argument(
        "--item",
        default=None,
        help="for_each item id (emits item_skipped instead of step_skipped)",
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="agent id (mutually exclusive with --human); defaults to 'cli' when neither given",
    )
    parser.add_argument(
        "--human",
        default=None,
        help="human name (mutually exclusive with --agent)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit exactly one machine-readable skip object on stdout",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code or 2)

    if sum(value is not None for value in (args.agent, args.human)) > 1:
        return _exit_recoverable("skip: --agent and --human are mutually exclusive")
    if args.agent is not None:
        actor_kind, actor_id = "agent", args.agent
    elif args.human is not None:
        actor_kind, actor_id = "human", args.human
    else:
        actor_kind, actor_id = "agent", "cli"

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        return _exit_recoverable(f"skip: {exc}")

    active_run = read_current_run_state(slug, root=projects_root)
    if active_run is None:
        return _exit_recoverable(
            f"skip: no active run for project {slug!r}",
            recovery=f"astrid start <orchestrator-id> --project {slug}",
        )

    run_id = active_run["run_id"]
    proj_root = project_dir(slug, root=projects_root)
    plan_path = proj_root / "plan.json"
    run_dir = proj_root / "runs" / run_id
    events_path = run_dir / "events.jsonl"

    plan = load_plan(plan_path)
    events = read_events(events_path)
    from astrid.core.task.plan_verbs import apply_mutations
    plan = apply_mutations(plan, events)

    step, path_tuple = _resolve_frontier_step(plan, events)
    if step is None:
        return _exit_recoverable(
            f"skip: run is exhausted",
            recovery=f"astrid abort --project {slug}",
        )

    expected_path = STEP_PATH_SEP.join(path_tuple)
    if args.step != expected_path:
        return _exit_recoverable(
            f"skip: step path {args.step!r} does not match cursor frontier "
            f"{expected_path!r}; only the current step may be skipped.",
            recovery=f"astrid next --project {slug}",
        )

    # --item: validate that the host has repeat.for_each and the item exists.
    if args.item is not None:
        repeat = getattr(step, "repeat", None)
        if not isinstance(repeat, RepeatForEach):
            return _exit_recoverable(
                f"skip: --item requires a step with repeat.for_each, "
                f"step {expected_path!r} has none",
            )
        # If the body step itself is required (optional=False on the host),
        # we still allow per-item skip — the spec calls out:
        #   "for_each parent with optional=False, item-level skip via --item:
        #    that item skipped, others run."
        # So we do NOT require step.optional=True for --item skip.
    else:
        if not step.optional:
            return _exit_recoverable(
                f"skip: step {expected_path!r} is not optional "
                f"(set optional=True in plan.json to allow skipping)",
            )

    # Build the event.
    if args.item is not None:
        event = make_item_skipped_event(
            path_tuple,
            args.item,
            actor_kind=actor_kind,
            actor_id=actor_id,
            reason=args.reason,
            step_version=step.version,
        )
    else:
        event = make_step_skipped_event(
            expected_path,
            actor_kind=actor_kind,
            actor_id=actor_id,
            reason=args.reason,
            step_version=step.version,
        )

    json_mode = bool(getattr(args, "json", False))

    try:
        with writer_context_for_project(slug, root=projects_root) as writer:
            writer.append(event)
    except StaleEpochError as exc:
        return _exit_recoverable(
            f"skip: stale writer_epoch ({exc}); re-run after the active "
            f"writer releases the lease",
        )
    except StaleTailError as exc:
        return _exit_recoverable(
            f"skip: stale events tail ({exc}); another writer appended "
            f"under us — re-run",
        )
    except EventLogError as exc:
        return _exit_recoverable(f"skip: {exc}")

    if json_mode:
        json_fields: dict = {
            "step_path": expected_path,
            "actor_kind": actor_kind,
            "actor_id": actor_id,
        }
        if args.item is not None:
            json_fields["kind"] = "item_skipped"
            json_fields["item_id"] = args.item
        else:
            json_fields["kind"] = "step_skipped"
        if args.reason:
            json_fields["reason"] = args.reason
        json_fields["step_version"] = step.version
        json_fields["next_command"] = f"astrid next --project {slug}"

        return emit_lifecycle_json(
            project=slug,
            run_id=run_id,
            state="skipped",
            **json_fields,
        )

    if args.item is not None:
        print(f"skipped item {args.item} of {expected_path}")
    else:
        print(f"skipped {expected_path}")
    return 0


__all__ = ["cmd_skip"]
