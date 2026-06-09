"""Session status JSON/text rendering.

Extracted from ``astrid.core.session.cli`` during M4 T48.
All status rendering functions live here; ``cmd_status`` is re-exported
through ``cli.py`` for backward-compatible monkeypatching.  Tests that
reference ``cli.cmd_status`` and ``cli.STATUS_UNBOUND_HEADER`` continue
to work via facade re-exports.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.project.current_run import read_current_run
from astrid.core.project.paths import project_dir
from astrid.core.session.binding import (
    SessionBindingError,
    resolve_current_session,
)
from astrid.core.session.config import resolve_default_project
from astrid.core.session.discovery import discover_projects
from astrid.core.session.identity import read_identity
from astrid.core.session.lease import (
    LeaseError,
    read_lease,
)
from astrid.core.session.model import Session
from astrid.core.session._shared import (
    NONE_PLACEHOLDER,
    TAKEOVER_HINT_ORPHAN,
    TAKEOVER_HINT_READER,
    _json_mode,
)
from astrid.core.task.cli_contract import emit_lifecycle_json
from astrid.core.task.events import EVENTS_FILENAME, read_events
from astrid.core.timeline import crud as timeline_crud
from astrid.core.timeline.defaults import read_project_default
from astrid.core.timeline.paths import find_timeline_slug_for_ulid
from astrid.core.util.log_and_swallow import log_and_swallow


# ----- Templates (tests assert on these literal strings; keep them stable) -----

STATUS_UNBOUND_HEADER = "no session bound"
ATTACH_SUGGESTION_TEMPLATE = "  astrid attach {slug}"
NO_PROJECTS_FOUND = "no projects discovered under the projects root"


# ----- Helpers ----------------------------------------------------------

def _status_state_for(role: str, run_id: str | None) -> str:
    if run_id is None:
        return "session_bound"
    if role == "lease-error":
        return "lease_error"
    return role.replace("-", "_")


def _compact_recent_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recent: list[dict[str, Any]] = []
    for ev in events[-5:]:
        recent.append(
            {
                "kind": str(ev.get("kind", "?")),
                "ts": str(ev.get("ts", "")),
            }
        )
    return recent


def _print_discovery_hints(*, out: Any) -> None:
    print("  astrid skills list          # discover pack skills and install state", file=out)
    print("  astrid orchestrators list   # discover workflows", file=out)
    print("  astrid executors list       # discover concrete tools", file=out)
    print("  astrid elements list        # discover render building blocks", file=out)


# ----- cmd_status -------------------------------------------------------


def cmd_status(args: argparse.Namespace, *, out: Any = None) -> int:
    if out is None:
        out = sys.stdout
    try:
        # T9 / FLAG-S1-003: INTENTIONALLY env-only (no slug=). ``session
        # status`` reports on the live env binding; pulling a file fallback
        # would mask the unbound-state it exists to surface.
        session = resolve_current_session()
    except SessionBindingError as exc:
        raise AstridError(f"status: {exc}", recovery_command="astrid status") from exc

    if session is None:
        if _json_mode(args):
            return _render_unbound_status_json(out=out)
        return _render_unbound_status(out=out)
    if _json_mode(args):
        return _render_bound_status_json(session, out=out)
    return _render_bound_status(session, out=out)


# ----- Unbound status rendering -----------------------------------------


def _render_unbound_status(*, out: Any) -> int:
    print(STATUS_UNBOUND_HEADER, file=out)
    default = resolve_default_project()
    projects = discover_projects()
    default_is_available = bool(default and default in projects)
    if default_is_available:
        print(f"default project: {default}", file=out)
    elif default:
        print(
            f"configured default project: {default} (not found under current projects root)",
            file=out,
        )
    if not projects:
        print(NO_PROJECTS_FOUND, file=out)
        print("create one with: astrid projects create <slug>", file=out)
        return 0
    print("", file=out)
    print("start:", file=out)
    if default_is_available:
        print("  astrid attach              # attach default project", file=out)
    elif len(projects) == 1:
        print(f"  astrid attach {projects[0]}", file=out)
    else:
        print("  astrid attach <project>", file=out)
    print("", file=out)
    print("discovered projects:", file=out)
    for slug in projects:
        print(ATTACH_SUGGESTION_TEMPLATE.format(slug=slug), file=out)
    print("", file=out)
    print("manage:", file=out)
    print("  astrid projects ls", file=out)
    if projects:
        print(f"  astrid projects default {projects[0]}", file=out)
    print("", file=out)
    print("after attach:", file=out)
    _print_discovery_hints(out=out)
    return 0


def _render_unbound_status_json(*, out: Any) -> int:
    default = resolve_default_project()
    projects = discover_projects()
    default_is_available = bool(default and default in projects)
    if default_is_available:
        next_command = "astrid attach"
    elif len(projects) == 1:
        next_command = f"astrid attach {projects[0]}"
    elif projects:
        next_command = "astrid attach <project>"
    else:
        next_command = "astrid projects create <slug>"
    return emit_lifecycle_json(
        project=None,
        run_id=None,
        state="no_session_bound",
        stream=out,
        session_id=None,
        default_project=default,
        default_project_available=default_is_available,
        discovered_projects=projects,
        next_command=next_command,
    )


# ----- Bound status rendering -------------------------------------------


def _render_bound_status(session: Session, *, out: Any) -> int:
    # Fix 2 (v6 dogfood): the per-tab ``--as agent:<slug>`` override is
    # written to ``session.agent_id`` at attach time and IS the per-tab
    # identity. Previously this preferred the on-disk identity record
    # (e.g., ``codex-1``), which silently masked the override — an agent
    # that ran ``attach --as agent:foo`` would see ``status`` report
    # ``agent: codex-1``. Trust the session record; fall back to the
    # on-disk identity only when the session has no agent_id pinned.
    agent_id = session.agent_id
    if not agent_id:
        identity = read_identity()
        agent_id = identity.agent_id if identity else session.agent_id
    # Try to pick up an on-disk run_id update (auto-rebind preview without
    # actually mutating the session file — that's WriterContext's job).
    on_disk_run_id = read_current_run(session.project)
    run_id = on_disk_run_id or session.run_id

    # Resolve timeline slug from timeline_id when needed.
    timeline_slug = session.timeline
    timeline_final_count = 0
    # Also fall back to project default when session has no timeline binding.
    if timeline_slug is None and session.timeline_id is None:
        default_ulid = read_project_default(session.project)
        if default_ulid is not None:
            default_slug = find_timeline_slug_for_ulid(
                session.project, default_ulid
            )
            if default_slug is not None:
                timeline_slug = default_slug
    if timeline_slug is not None or session.timeline_id is not None:
        if timeline_slug is None and session.timeline_id is not None:
            timeline_slug = find_timeline_slug_for_ulid(
                session.project, session.timeline_id
            )
        if timeline_slug is not None:
            try:
                data = timeline_crud.show_timeline(session.project, timeline_slug)
                if data is not None:
                    timeline_final_count = len(data["manifest"].final_outputs)
            except Exception as exc:  # noqa: BLE001
                # best-effort; don't break status for a corrupt timeline
                log_and_swallow(exc, context="session.cli.status.timeline_count")

    timeline_line = f"timeline: {timeline_slug or NONE_PLACEHOLDER}"
    if timeline_final_count > 0:
        plural = "s" if timeline_final_count != 1 else ""
        timeline_line += f" ({timeline_final_count} final output{plural})"

    print(f"session: {session.id}", file=out)
    print(f"agent: {agent_id}", file=out)
    print(f"project: {session.project}", file=out)
    print(timeline_line, file=out)
    print(f"run: {run_id or NONE_PLACEHOLDER}", file=out)

    current_step = NONE_PLACEHOLDER
    last_five: list[dict[str, Any]] = []
    inbox_count = 0
    role_line = f"role: {session.role}"
    takeover_hint: str | None = None

    if run_id is not None:
        run_dir = project_dir(session.project) / "runs" / run_id
        events_path = run_dir / EVENTS_FILENAME
        if events_path.exists():
            events = read_events(events_path)
            last_five = events[-5:]
            # "current step" proxy: latest step_dispatched event, else last
            # event kind. Sprint 1 is not the step-model rewrite (Sprint 3).
            for ev in reversed(events):
                if ev.get("kind") == "step_dispatched":
                    current_step = str(ev.get("plan_step_id") or ev.get("kind"))
                    break
            else:
                if events:
                    current_step = str(events[-1].get("kind", NONE_PLACEHOLDER))
        inbox_dir = run_dir / "inbox"
        if inbox_dir.exists():
            inbox_count = sum(1 for p in inbox_dir.iterdir() if p.is_file())
        # Role correction from the lease (the on-disk session role is just
        # a hint; the lease is authoritative).
        lease_error: str | None = None
        try:
            lease = read_lease(run_dir)
        except LeaseError as exc:
            lease = {"attached_session_id": None}
            lease_error = str(exc)
        attached = lease.get("attached_session_id")
        if lease_error is not None:
            role_line = "role: lease-error"
            takeover_hint = (
                f"lease error: {lease_error}; recovery: inspect {run_id}/lease.json "
                "or migrate legacy active_run.json before writing"
            )
        elif attached is None:
            role_line = "role: orphan-pending"
            takeover_hint = TAKEOVER_HINT_ORPHAN.format(run_id=run_id)
        elif attached != session.id:
            role_line = "role: reader"
            takeover_hint = TAKEOVER_HINT_READER.format(writer=attached, run_id=run_id)
        else:
            role_line = "role: writer"

    print(f"current step: {current_step}", file=out)
    print("recent events (last 5):", file=out)
    if not last_five:
        print(f"  {NONE_PLACEHOLDER}", file=out)
    else:
        for ev in last_five:
            ts = ev.get("ts", "")
            kind = ev.get("kind", "?")
            print(f"  {kind} @ {ts}", file=out)
    print(f"inbox: {inbox_count}", file=out)
    print(role_line, file=out)
    if takeover_hint is not None:
        print(takeover_hint, file=out)
    print("", file=out)
    print("task:", file=out)
    if run_id is not None:
        print(
            f"  astrid next --project {session.project}   # continue current task run",
            file=out,
        )
    else:
        print(
            f"  astrid start <orchestrator-id> --project {session.project}   # start a task list",
            file=out,
        )
    print("", file=out)
    print("discover:", file=out)
    _print_discovery_hints(out=out)
    return 0


def _render_bound_status_json(session: Session, *, out: Any) -> int:
    agent_id = session.agent_id
    if not agent_id:
        identity = read_identity()
        agent_id = identity.agent_id if identity else session.agent_id

    on_disk_run_id = read_current_run(session.project)
    run_id = on_disk_run_id or session.run_id

    timeline_slug = session.timeline
    timeline_final_count = 0
    if timeline_slug is None and session.timeline_id is None:
        default_ulid = read_project_default(session.project)
        if default_ulid is not None:
            default_slug = find_timeline_slug_for_ulid(session.project, default_ulid)
            if default_slug is not None:
                timeline_slug = default_slug
    if timeline_slug is None and session.timeline_id is not None:
        timeline_slug = find_timeline_slug_for_ulid(session.project, session.timeline_id)
    if timeline_slug is not None:
        try:
            data = timeline_crud.show_timeline(session.project, timeline_slug)
            if data is not None:
                timeline_final_count = len(data["manifest"].final_outputs)
        except Exception as exc:  # noqa: BLE001
            log_and_swallow(exc, context="session.cli.status.timeline_count")

    current_step = NONE_PLACEHOLDER
    recent_events: list[dict[str, Any]] = []
    inbox_count = 0
    role = str(session.role)
    takeover_hint: str | None = None
    lease_error: str | None = None

    if run_id is not None:
        run_dir = project_dir(session.project) / "runs" / run_id
        events_path = run_dir / EVENTS_FILENAME
        if events_path.exists():
            events = read_events(events_path)
            recent_events = _compact_recent_events(events)
            for ev in reversed(events):
                if ev.get("kind") == "step_dispatched":
                    current_step = str(ev.get("plan_step_id") or ev.get("kind"))
                    break
            else:
                if events:
                    current_step = str(events[-1].get("kind", NONE_PLACEHOLDER))
        inbox_dir = run_dir / "inbox"
        if inbox_dir.exists():
            inbox_count = sum(1 for p in inbox_dir.iterdir() if p.is_file())
        try:
            lease = read_lease(run_dir)
        except LeaseError as exc:
            lease = {"attached_session_id": None}
            lease_error = str(exc)
        attached = lease.get("attached_session_id")
        if lease_error is not None:
            role = "lease-error"
            takeover_hint = (
                f"lease error: {lease_error}; recovery: inspect {run_id}/lease.json "
                "or migrate legacy active_run.json before writing"
            )
        elif attached is None:
            role = "orphan-pending"
            takeover_hint = TAKEOVER_HINT_ORPHAN.format(run_id=run_id)
        elif attached != session.id:
            role = "reader"
            takeover_hint = TAKEOVER_HINT_READER.format(writer=attached, run_id=run_id)
        else:
            role = "writer"

    task_command = (
        f"astrid next --project {session.project}"
        if run_id is not None
        else f"astrid start <orchestrator-id> --project {session.project}"
    )
    return emit_lifecycle_json(
        project=session.project,
        run_id=run_id,
        state=_status_state_for(role, run_id),
        stream=out,
        session_id=session.id,
        agent_id=agent_id,
        timeline=timeline_slug,
        timeline_final_output_count=timeline_final_count,
        current_step=current_step,
        recent_events=recent_events,
        inbox_count=inbox_count,
        role=role,
        takeover_hint=takeover_hint,
        task_command=task_command,
        lease_error=lease_error,
    )
