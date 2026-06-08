"""Resolve the current tab's session from ``ASTRID_SESSION_ID``.

The session record is the authoritative binding for a tab; the env var
just points at it. Subprocesses inherit ``ASTRID_SESSION_ID`` (Sprint 0
env-inheritance spike confirms this); do not silently scrub it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from astrid.core.contracts.errors import AstridError
from astrid.core.project.paths import project_dir
from astrid.core.session.lease import read_lease
from astrid.core.session.model import Session, SessionValidationError
from astrid.core.session.paths import session_path

ASTRID_SESSION_ID_ENV = "ASTRID_SESSION_ID"


class SessionBindingError(AstridError):
    """Raised when the session-binding env var points at a missing/invalid record."""

    def __init__(self, cause: str) -> None:
        super().__init__(cause)


SESSION_FILE_NAME = ".astrid-session"
AttachMode = Literal["created", "opened"]


@dataclass(frozen=True)
class AttachSessionResult:
    mode: AttachMode
    session: Session


def attach_session(
    *,
    project_slug: str,
    agent_id: str,
    projects_root: str | Path,
    session_root: str | Path,
    session_id: str | None = None,
    timeline: str | None = None,
    timeline_id: str | None = None,
    attached_at: str | None = None,
    opened_at: str | None = None,
    write_project_pointer: bool = False,
) -> AttachSessionResult:
    """Create or open a session using only explicit roots and supplied identity.

    This is the SDK-facing attach primitive. It does not prompt, print, read
    identity files, consult ``ASTRID_HOME``/``Path.home()``, or write the
    project pointer unless ``write_project_pointer`` is true.
    """

    from astrid.core.session.lifecycle import create_session, open_session

    if session_id is None:
        return AttachSessionResult(
            mode="created",
            session=create_session(
                project_slug=project_slug,
                agent_id=agent_id,
                projects_root=projects_root,
                session_root=session_root,
                timeline=timeline,
                timeline_id=timeline_id,
                attached_at=attached_at,
                last_used_at=opened_at,
                write_project_pointer=write_project_pointer,
            ),
        )

    return AttachSessionResult(
        mode="opened",
        session=open_session(
            session_id,
            project_slug=project_slug,
            agent_id=agent_id,
            projects_root=projects_root,
            session_root=session_root,
            opened_at=opened_at,
            write_project_pointer=write_project_pointer,
        ),
    )


# T9 / FLAG-S1-003: callers that PASS `slug=` get the file fallback. The
# following ~6 test/utility callers intentionally do NOT pass slug and rely
# on env-only resolution (test conftest fixtures bind ASTRID_SESSION_ID
# directly; spike tests assert env-inheritance specifically):
#   - tests/conftest.py (autouse fixtures seed env)
#   - tests/test_threads_cli.py (env-driven coverage)
#   - tests/test_task_hook_stop.py (env-binding round-trip)
#   - tests/spikes/test_env_inheritance.py (env-inheritance spike — must
#     stay env-only by design or the spike's invariant is meaningless)
#   - astrid/core/session/cli.py:cmd_takeover (`session takeover`) — starts
#     env-only so it can distinguish bound takeover from the explicit
#     unbound bootstrap path; filesystem fallback would mask that branch
#   - astrid/core/session/cli.py:cmd_takeover detach branch (~:505) — same
# `resolve_current_session` MUST NEVER walk the filesystem to discover the
# slug; callers that have a slug in hand pass it; callers that don't get
# env-only resolution.

def resolve_current_session_with_fs_fallback(
    slug: str | None = None,
    *,
    projects_root: "Path | str | None" = None,
    on_auto_resolve: "Callable[[str], None] | None" = None,
) -> Session | None:
    """CLI-gate variant of :func:`resolve_current_session` that walks the
    projects-root to discover a single ``.astrid-session`` when no
    ``ASTRID_SESSION_ID`` is set and no ``slug`` is passed.

    This is the gate-friendly counterpart to ``resolve_current_session``
    (which intentionally never walks the filesystem — see FLAG-S1-003).
    The pipeline gate calls this so every verb gets the same auto-resolve
    behavior that ``astrid next`` already enjoys (Fix 1, v6 dogfood
    follow-up): an agent that ran ``astrid attach <proj>`` in a prior
    shell no longer has to ``export ASTRID_SESSION_ID=...`` before each
    subsequent command.

    Behavior:
      * ``ASTRID_SESSION_ID`` set → identical to ``resolve_current_session``.
      * ``ASTRID_SESSION_ID`` unset AND ``slug`` provided → identical
        (file-bound fallback for that slug).
      * ``ASTRID_SESSION_ID`` unset AND ``slug`` is ``None`` →
        scan ``projects_root`` for exactly one ``.astrid-session`` file.
        Refuse if >1 exist (concurrency guard mirrors the policy in
        ``_most_recent_session_slug``).

    ``on_auto_resolve(slug)`` is called when the filesystem fallback
    fires; the caller uses it to nudge the operator about which session
    was picked (stderr, mirroring ``astrid next``).
    """
    raw = os.environ.get(ASTRID_SESSION_ID_ENV)
    if not raw and slug is None:
        from astrid.core.session.discovery_hints import _most_recent_session_slug

        root = Path(projects_root) if projects_root is not None else None
        discovered = _most_recent_session_slug(root)
        if discovered is not None:
            slug = discovered
            if on_auto_resolve is not None:
                try:
                    on_auto_resolve(discovered)
                except Exception:
                    pass
    return resolve_current_session(slug=slug)


def resolve_current_session(slug: str | None = None) -> Session | None:
    """Return the current tab's :class:`Session`, or ``None`` if unbound.

    Resolution order:
      1. ``ASTRID_SESSION_ID`` env var (explicit).
      2. ``<projects_root>/<slug>/.astrid-session`` (only when ``slug`` provided).
      3. ``None``.

    Unbound = ``ASTRID_SESSION_ID`` is unset OR set to an empty string AND
    no file-bound fallback resolved. The CLI gate (T8) converts ``None``
    into a "no session bound" error for verbs outside the unbound allowlist.
    """

    raw = os.environ.get(ASTRID_SESSION_ID_ENV)
    if not raw and slug:
        # File-bound fallback. NEVER walks the filesystem.
        try:
            from astrid.core.project.paths import project_dir as _project_dir
            file_path = _project_dir(slug) / SESSION_FILE_NAME
            if file_path.is_file():
                content = file_path.read_text(encoding="utf-8").strip()
                # Accept either bare id or `ASTRID_SESSION_ID=<id>` form.
                if "=" in content:
                    key, _, value = content.partition("=")
                    if key.strip() == ASTRID_SESSION_ID_ENV:
                        raw = value.strip()
                else:
                    raw = content
        except Exception:
            raw = raw or None
    if not raw:
        return None
    path = session_path(raw)
    try:
        return Session.from_json(path)
    except FileNotFoundError as exc:
        raise SessionBindingError(
            f"ASTRID_SESSION_ID={raw!r} but no session file at {path}; "
            "did you `astrid attach <project>` or detach?"
        ) from exc
    except SessionValidationError as exc:
        raise SessionBindingError(
            f"ASTRID_SESSION_ID={raw!r} points at a malformed session file: {exc}"
        ) from exc


def is_writer_for(session: Session, run_dir: str | Path) -> bool:
    """Return True iff this session currently holds the lease for ``run_dir``."""

    lease = read_lease(run_dir)
    return lease.get("attached_session_id") == session.id


def current_run_dir(session: Session, *, root: str | Path | None = None) -> Path | None:
    """Return the project active-run directory from ``current_run.json``.

    The session record may lag another tab's run start or takeover. Keep the
    project pointer authoritative and let writer/session lifecycle paths handle
    rebinding when they need to mutate the session record.
    """

    from astrid.core.project.current_run import read_current_run

    run_id = read_current_run(session.project, root=root)
    if run_id is None:
        return None
    return project_dir(session.project, root=root) / "runs" / run_id
