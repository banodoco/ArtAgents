"""Explicit-root SDK lifecycle helpers for session records.

These helpers are intentionally print-free and prompt-free. CLI wrappers are
responsible for user interaction, default discovery, and identity bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.current_run import read_current_run
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV, SESSION_FILE_NAME
from astrid.core.session.lease import (
    LeaseTakeoverResult,
    mutate_lease_for_takeover,
    read_lease,
)
from astrid.core.task.events import EVENTS_FILENAME
from astrid.core.threads.ids import generate_ulid

from .model import Session, SessionRole, SessionStore, now_iso


class SessionLifecycleError(RuntimeError):
    """Base error for explicit-root lifecycle operations."""


class SessionTakeoverTargetError(SessionLifecycleError):
    """Raised when a takeover/recovery target cannot be resolved safely."""


@dataclass(frozen=True)
class TakeoverTarget:
    """Resolved task-run target for a prompt-free takeover/recovery call."""

    project_slug: str
    run_id: str
    run_dir: Path
    prev_session_id: str | None


@dataclass(frozen=True)
class SessionTakeoverResult:
    """Structured result from a prompt-free takeover/recovery mutation."""

    operation: str
    session: Session
    target: TakeoverTarget
    lease: dict[str, Any]


def create_session(
    *,
    project_slug: str,
    agent_id: str,
    projects_root: str | Path,
    session_root: str | Path,
    timeline: str | None = None,
    timeline_id: str | None = None,
    session_id: str | None = None,
    attached_at: str | None = None,
    last_used_at: str | None = None,
    write_project_pointer: bool = False,
) -> Session:
    """Create and persist a new session record under ``session_root``."""

    sid = session_id or generate_ulid()
    role, run_id = _derive_role_and_run_id(
        project_slug=project_slug,
        session_id=sid,
        projects_root=projects_root,
    )
    attached = attached_at or now_iso()
    session = Session(
        id=sid,
        project=project_slug,
        agent_id=agent_id,
        attached_at=attached,
        last_used_at=last_used_at or attached,
        role=role,
        timeline=timeline,
        timeline_id=timeline_id,
        run_id=run_id,
    )
    SessionStore(session_root=session_root).save(session)
    if write_project_pointer:
        write_session_pointer(
            project_slug=project_slug,
            session_id=session.id,
            projects_root=projects_root,
        )
    return session


def save_session(session: Session, *, session_root: str | Path) -> Path:
    """Persist ``session`` under ``session_root`` and return its file path."""

    return SessionStore(session_root=session_root).save(session)


def load_session(session_id: str, *, session_root: str | Path) -> Session:
    """Load ``session_id`` from ``session_root`` without mutating the record."""

    return SessionStore(session_root=session_root).load(session_id)


def open_session(
    session_id: str,
    *,
    project_slug: str,
    agent_id: str,
    projects_root: str | Path,
    session_root: str | Path,
    opened_at: str | None = None,
    write_project_pointer: bool = False,
) -> Session:
    """Load ``session_id`` and refresh ``last_used_at`` in-place."""

    store = SessionStore(session_root=session_root)
    session = store.load(session_id)
    role, run_id = _derive_role_and_run_id(
        project_slug=project_slug,
        session_id=session.id,
        projects_root=projects_root,
    )
    refreshed = session.with_changes(
        project=project_slug,
        agent_id=agent_id,
        run_id=run_id,
        role=role,
        last_used_at=opened_at or now_iso(),
    )
    store.save(refreshed)
    if write_project_pointer:
        write_session_pointer(
            project_slug=project_slug,
            session_id=refreshed.id,
            projects_root=projects_root,
        )
    return refreshed


def resolve_takeover_target(
    target: str,
    *,
    caller_session: Session,
    projects_root: str | Path,
    session_root: str | Path,
) -> TakeoverTarget:
    """Resolve a session-id or run-id takeover target without mutation.

    Session-id targets are loaded from the explicit ``session_root``. Run-id
    targets are resolved inside the caller session's project under the explicit
    ``projects_root``. This helper never scans global defaults, prompts, writes
    sessions, or creates run/event files.
    """

    store = SessionStore(session_root=session_root)
    session_path = store.session_path(target)
    if session_path.exists():
        target_session = store.load(target)
        if target_session.run_id is None:
            raise SessionTakeoverTargetError(
                f"target session {target!r} is not bound to a run"
            )
        run_dir = (
            project_dir(target_session.project, root=projects_root)
            / "runs"
            / target_session.run_id
        )
        _raise_if_missing_run(run_dir, target_session.run_id)
        return TakeoverTarget(
            project_slug=target_session.project,
            run_id=target_session.run_id,
            run_dir=run_dir,
            prev_session_id=target_session.id,
        )

    run_dir = project_dir(caller_session.project, root=projects_root) / "runs" / target
    _raise_if_missing_run(run_dir, target)
    return TakeoverTarget(
        project_slug=caller_session.project,
        run_id=target,
        run_dir=run_dir,
        prev_session_id=None,
    )


def recover_session(
    *,
    caller_session: Session,
    projects_root: str | Path,
    session_root: str | Path,
    force: bool = False,
    recovered_at: str | None = None,
    write_project_pointer: bool = False,
) -> SessionTakeoverResult:
    """Recover the caller project's active run from ``current_run.json``.

    ``current_run.json`` is the active-run pointer: this function reads it
    first, then requires the target lease to exist before mutating anything.
    """

    run_id = read_current_run(caller_session.project, root=projects_root)
    if run_id is None:
        raise SessionTakeoverTargetError(
            f"project {caller_session.project!r} has no current_run.json active run"
        )
    return takeover_session(
        caller_session=caller_session,
        target=run_id,
        projects_root=projects_root,
        session_root=session_root,
        force=force,
        reason="recover",
        taken_over_at=recovered_at,
        write_project_pointer=write_project_pointer,
    )


def takeover_session(
    *,
    caller_session: Session,
    target: str,
    projects_root: str | Path,
    session_root: str | Path,
    force: bool = False,
    reason: str = "takeover",
    taken_over_at: str | None = None,
    write_project_pointer: bool = False,
) -> SessionTakeoverResult:
    """Take over ``target`` and promote ``caller_session`` to writer.

    The mutation order is intentionally lease-first:

    1. Resolve the target and preflight its canonical lease without mutation.
    2. Mutate the lease and append the takeover event under the events lock.
    3. Persist the caller session as writer and optionally update the project
       ``.astrid-session`` pointer.

    If target resolution, lease preflight, warm-target checks, or locked lease
    mutation fail, the caller session file is not written by this helper.
    """

    resolved = resolve_takeover_target(
        target,
        caller_session=caller_session,
        projects_root=projects_root,
        session_root=session_root,
    )

    mutation: LeaseTakeoverResult = mutate_lease_for_takeover(
        resolved.run_dir,
        new_session_id=caller_session.id,
        prev_session_id=resolved.prev_session_id,
        reason=reason,
        force=force,
    )

    promoted = caller_session.with_changes(
        project=resolved.project_slug,
        run_id=resolved.run_id,
        role="writer",
        last_used_at=taken_over_at or now_iso(),
    )
    SessionStore(session_root=session_root).save(promoted)
    if write_project_pointer:
        write_session_pointer(
            project_slug=resolved.project_slug,
            session_id=promoted.id,
            projects_root=projects_root,
        )
    return SessionTakeoverResult(
        operation=mutation.operation,
        session=promoted,
        target=resolved,
        lease=mutation.lease,
    )


def write_session_pointer(
    *,
    project_slug: str,
    session_id: str,
    projects_root: str | Path,
) -> Path:
    """Write ``<projects_root>/<project_slug>/.astrid-session`` explicitly."""

    session_file = project_dir(project_slug, root=projects_root) / SESSION_FILE_NAME
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        f"{ASTRID_SESSION_ID_ENV}={session_id}\n", encoding="utf-8"
    )
    try:
        session_file.chmod(0o600)
    except OSError:
        pass
    return session_file


def _raise_if_missing_run(run_dir: Path, run_id: str) -> None:
    if not run_dir.is_dir():
        raise SessionTakeoverTargetError(
            f"target run {run_id!r} does not exist at {run_dir}"
        )
    events_path = run_dir / EVENTS_FILENAME
    if events_path.exists() and not events_path.is_file():
        raise SessionTakeoverTargetError(
            f"target run {run_id!r} has invalid events path {events_path}"
        )


def _derive_role_and_run_id(
    *,
    project_slug: str,
    session_id: str,
    projects_root: str | Path,
) -> tuple[SessionRole, str | None]:
    """Derive the session role from canonical current-run plus lease state."""

    on_disk_run_id = read_current_run(project_slug, root=projects_root)
    if on_disk_run_id is None:
        return "writer", None

    run_dir = project_dir(project_slug, root=projects_root) / "runs" / on_disk_run_id
    lease = read_lease(run_dir)
    attached = lease.get("attached_session_id")
    if attached is None:
        return "orphan-pending", on_disk_run_id
    if attached != session_id:
        return "reader", on_disk_run_id
    return "writer", on_disk_run_id
