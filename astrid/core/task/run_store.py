"""Phase 5 lifecycle verbs: start/abort/status/runs ls/next; cmd_ack lives
in lifecycle_ack.py to keep both modules under the size budget.

cmd_runs_ls (FLAG-P5-006): natural completion does not clear active_run.json
in V1, so the lister surfaces only 'aborted' vs 'in-progress'.
cmd_start (SD-007): does not silently invoke compile when the pre-built JSON
manifest is missing — prints the compile recovery and returns non-zero.
Author-test replays are the exception: they deliberately use compiled smoke
plans even for orchestrators that normally build dynamic start plans.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from astrid.contracts.run_status import RunStatus
from astrid.core.project.current_run import (
    clear_current_run,
    read_current_run,
)
from astrid.core.project.paths import (
    project_dir,
    resolve_projects_root,
    validate_project_slug,
    validate_run_id,
)
from astrid.core.session.lease import (
    release_writer_lease,
)
from astrid.core.session.writer import writer_context_for_project
from astrid.core.task.events import (
    make_run_aborted_event,
    make_run_completed_event,
    make_step_awaiting_fetch_event,
    make_step_completed_event,
    make_step_failed_event,
    read_events,
)
from astrid.core.task.cli_contract import emit_lifecycle_json
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    find_step_by_path,
    load_plan,
)
from astrid.core.task.run_state import _run_is_complete


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _system_exit_code(exc: SystemExit) -> int:
    return int(exc.code) if isinstance(exc.code, int) else 2


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

def cmd_abort(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(prog="astrid abort", add_help=True)
    parser.add_argument("--project", required=True, help="project slug")
    parser.add_argument("--reason", default=None, help="optional human-readable reason")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit exactly one machine-readable abort object on stdout",
    )
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)

    try:
        slug = validate_project_slug(args.project)
    except Exception as exc:
        _print_err(f"abort: {exc}")
        return 1

    json_mode = bool(args.json)
    run_id = read_current_run(slug, root=projects_root)
    if run_id is None:
        # Idempotent — Phase 6 Stop-hook may invoke abort defensively.
        if json_mode:
            return emit_lifecycle_json(
                project=slug,
                run_id=None,
                state="no_active_run",
            )
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
    if json_mode:
        return emit_lifecycle_json(
            project=slug,
            run_id=run_id,
            state="aborted",
        )
    print(f"aborted {run_id}")
    return 0

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
        return _summarize_run_json_status(run_dir), "", ""
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


def _summarize_run_json_status(run_dir: Path) -> str:
    run_json_path = run_dir / "run.json"
    if not run_json_path.is_file():
        return "in-flight"
    try:
        raw = json.loads(run_json_path.read_text(encoding="utf-8"))
        status = raw.get("status") if isinstance(raw, dict) else None
        if isinstance(status, str):
            parsed = RunStatus.from_run_record_status(status)
            return "in-flight" if parsed is RunStatus.RUNNING else parsed.value
    except (OSError, ValueError, json.JSONDecodeError):
        return "in-flight"
    return "in-flight"


_RUNS_LS_STATUSES = ("completed", "in-flight", "aborted", "failed", "blocked", "skipped")


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
    parser.add_argument("--json", action="store_true", help="emit run summaries as JSON")
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

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "run_id": run_id,
                        "status": status,
                        "started_at": last_ts or None,
                        "summary": last_kind or None,
                    }
                    for _slug, run_id, status, last_kind, last_ts in rows
                ],
                sort_keys=True,
            )
        )
        return 0

    for slug, run_id, status, last_kind, last_ts in rows:
        print(f"{slug}\t{run_id}\t{status}\t{last_kind}\t{last_ts}")
    return 0

def cmd_step_retry_fetch(
    argv: Sequence[str],
    *,
    projects_root: Optional[Path] = None,
) -> int:
    """Retry fetching artifacts for a remote-artifact step awaiting fetch."""
    parser = argparse.ArgumentParser(prog="astrid step retry-fetch", add_help=True)
    parser.add_argument("step")
    parser.add_argument("--project", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--item", default=None, help="for_each item id")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return int(exc.code)

    from astrid.core.adapter import RunContext
    from astrid.core.adapter.remote_artifact_fetch import fetch_artifacts

    slug = validate_project_slug(args.project)
    run_id = validate_run_id(args.run)
    proj_root = project_dir(slug, root=projects_root)
    run_dir = proj_root / "runs" / run_id
    events_path = run_dir / "events.jsonl"
    plan = load_plan(proj_root / "plan.json")
    events = read_events(events_path)
    step_path = tuple(args.step.split(STEP_PATH_SEP))
    step = find_step_by_path(plan, step_path)
    if step is None:
        _print_err(f"step retry-fetch: unknown step {args.step!r}")
        return 1
    if step.adapter != "remote-artifact":
        _print_err(f"step retry-fetch: {args.step} is not a remote-artifact step")
        return 1
    if step.version != 1 and not any(
        event.get("step_version") == step.version and event.get("plan_step_path") == list(step_path)
        for event in events
    ):
        _print_err(f"step retry-fetch: no v{step.version} events found for {args.step}")
        return 1
    latest = None
    for event in reversed(events):
        if not (
            event.get("plan_step_path") == list(step_path)
            or event.get("plan_step_id") == args.step
        ):
            continue
        event_version = event.get("step_version", 1)
        if event_version == step.version:
            latest = event
            break
    if latest and latest.get("kind") == "step_completed":
        print(f"step retry-fetch: {args.step} already completed")
        return 0
    if not latest or latest.get("kind") != "step_awaiting_fetch":
        _print_err(f"step retry-fetch: {args.step} is not awaiting_fetch")
        return 1

    ctx = RunContext(
        slug=slug,
        run_id=run_id,
        project_root=proj_root,
        plan_step_path=step_path,
        step_version=step.version,
        item_id=args.item,
    )
    result = fetch_artifacts(step, ctx)
    if result.status == "completed":
        with writer_context_for_project(slug, root=projects_root) as writer:
            writer.append(
                make_step_completed_event(
                    args.step,
                    0,
                    adapter=step.adapter,
                    step_version=step.version,
                )
            )
        events = read_events(events_path)
        if _run_is_complete(plan, events):
            _emit_run_completed_if_needed(plan, events, events_path, run_id, slug=slug, projects_root=projects_root)
        return 0
    if result.status == "awaiting_fetch":
        with writer_context_for_project(slug, root=projects_root) as writer:
            writer.append(
                make_step_awaiting_fetch_event(
                    args.step,
                    missing=result.missing,
                    mismatched=result.mismatched,
                    reason=result.reason,
                    adapter=step.adapter,
                    step_version=step.version,
                )
            )
        return 1
    with writer_context_for_project(slug, root=projects_root) as writer:
        writer.append(
            make_step_failed_event(
                args.step,
                1,
                reason=result.reason,
                adapter=step.adapter,
                step_version=step.version,
            )
        )
    return 1
