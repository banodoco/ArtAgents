"""WriterContext: the session-scoped gate around every mutating verb.

Sprint 1 writer-boundary contract:

* Normal production task-run mutations flow through
  ``TaskRunWriter``/``WriterContext.append()``. The context resolves the bound
  session, performs any legacy active/current-run migration before writer-auth,
  reads the canonical lease, and carries the captured writer epoch into the
  locked append.
* ``astrid.core.task.events`` stays a generic event transport layer. It does
  not know about sessions or projects; production command code must not call
  raw append helpers directly for task-run events.
* Missing or malformed canonical lease state is a hard writer-auth failure
  after migration has had its chance to repair legacy state. Do not paper over
  lease read errors by treating a task run as orphaned.

On entry, WriterContext:

1. Reads ``<project>/current_run.json``. If the on-disk ``run_id`` does not
   match ``session.run_id``, the session is auto-rebound to the on-disk
   run id via :func:`dataclasses.replace`, **and the on-disk session file
   is rewritten** to match. This is a deliberate side effect: tests that
   snapshot the session file before invoking a verb must re-read after via
   the ``attached_session`` fixture's ``refresh()`` helper.
2. If ``session.run_id`` is still ``None`` after the rebind step (no run
   has been started yet), raises :class:`NoRunBoundError` — a
   session-state condition, defined LOCALLY in this module (NOT in
   ``events.py``; the event log is fine, the session is just not pointing
   at a run).
3. Reads ``runs/<run_id>/lease.json`` and performs the WRITER-AUTH CHECK:
   if ``lease['attached_session_id'] != session.id`` → :class:`NotWriterError`.
4. Captures ``expected_writer_epoch`` and ``plan_hash`` from the lease for
   use by :meth:`append`.

Inside the ``with`` block, :meth:`append` is the only sanctioned way to
write to ``events.jsonl``: it routes through
:func:`append_event_locked` with the captured epoch and a freshly-read tail
(both under flock). A stale writer that lost a takeover between
``__enter__`` and ``append`` is rejected at append time by the stale-epoch
CAS.

:func:`writer_context_from_decision` is the factory used by post-dispatch
``record_*`` helpers in ``gate.py``: it accepts a ``GateDecision``-shaped
object (any object exposing ``.session``) and produces a fresh
WriterContext that performs the same writer-auth check on entry.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from astrid.core.project.current_run import read_current_run
from astrid.core.session.current_run_state import (
    migrate_legacy_active_run_before_writer_auth,
)
from astrid.core.foundation.project_paths import project_dir
from astrid.core.session.model import Session, now_iso
from astrid.core.session.paths import session_path
from astrid.core.task.events import (
    NotWriterError,
    append_event_locked,
)


class NoRunBoundError(Exception):
    """The active session has no ``run_id`` to write against.

    Session-state condition. Distinct from the event-log CAS errors
    (StaleTailError / StaleEpochError / NotWriterError) which live in
    :mod:`astrid.core.task.events`. Callers typically respond by either
    prompting the user to ``astrid start`` a run or surfacing the error.
    """

    def __init__(self, session_id: str, project: str) -> None:
        self.session_id = session_id
        self.project = project
        super().__init__(
            f"session {session_id!r} is bound to project {project!r} but has no run_id; "
            "start a run before mutating verbs"
        )


class _HasSession(Protocol):
    """Structural type for the ``GateDecision`` factory contract.

    T8/T9 extend ``GateDecision`` with ``run_dir`` / ``writer_epoch_at_dispatch``
    / ``session_id`` fields; T6 only needs ``.session`` and re-derives the
    rest from disk so the factory works regardless of how those fields are
    populated.
    """

    session: Session


@dataclass(frozen=True)
class TaskRunWriter:
    """Authenticated task-run writer state captured from the canonical lease."""

    session: Session
    run_dir: Path
    expected_writer_epoch: int
    plan_hash: str


def open_task_run_writer(
    session: Session,
    *,
    root: str | Path | None = None,
    session_root: str | Path | None = None,
) -> TaskRunWriter:
    """Authenticate ``session`` as the current task-run writer.

    Legacy active/current-run migration gets exactly one chance before the
    canonical lease read. After that, missing or malformed lease state fails
    closed and only the session id named in ``lease.attached_session_id`` may
    mutate the run.
    """

    from astrid.core.session import lease as lease_mod

    migrate_legacy_active_run_before_writer_auth(
        session.project,
        root=root,
        session_id=session.id,
    )

    on_disk_run_id = read_current_run(session.project, root=root)
    if on_disk_run_id != session.run_id:
        session = replace(session, run_id=on_disk_run_id, last_used_at=now_iso())
        if session_root is None:
            session.to_json(session_path(session.id))
        else:
            from astrid.core.session.model import SessionStore

            SessionStore(session_root=session_root).save(session)

    if session.run_id is None:
        raise NoRunBoundError(session.id, session.project)

    run_dir = project_dir(session.project, root=root) / "runs" / session.run_id
    lease_path = run_dir / lease_mod.LEASE_FILENAME
    if not lease_path.is_file():
        raise lease_mod.LeaseError(f"missing lease {lease_path}")

    lease = lease_mod.read_lease(run_dir)
    attached = lease.get("attached_session_id")
    if attached != session.id:
        raise NotWriterError(session_id=session.id, writer_id=attached)
    return TaskRunWriter(
        session=session,
        run_dir=run_dir,
        expected_writer_epoch=lease["writer_epoch"],
        plan_hash=lease["plan_hash"],
    )


def writer_context_for_project(
    slug: str,
    *,
    root: str | Path | None = None,
    session_root: str | Path | None = None,
) -> WriterContext:
    """Resolve the bound session for ``slug`` and return a WriterContext.

    Command modules use this at mutating boundaries instead of reading
    ``lease.json`` directly. The returned context still performs the normal
    migration, lease existence, session-id, and epoch capture checks on entry.
    """

    from astrid.core.session.binding import resolve_current_session

    session = resolve_current_session(slug=slug)
    if session is None:
        raise NoRunBoundError("", slug)
    return WriterContext(session, root=root, session_root=session_root)


class WriterContext:
    """Auto-rebinding writer-auth gate around the locked event-append helper."""

    def __init__(
        self,
        session: Session,
        *,
        root: str | Path | None = None,
        session_root: str | Path | None = None,
    ) -> None:
        self.session: Session = session
        self._root = root
        self._session_root = session_root
        self.run_dir: Path | None = None
        self.expected_writer_epoch: int = -1
        self.plan_hash: str = ""

    def __enter__(self) -> "WriterContext":
        writer = open_task_run_writer(
            self.session,
            root=self._root,
            session_root=self._session_root,
        )
        self.session = writer.session
        self.run_dir = writer.run_dir
        self.expected_writer_epoch = writer.expected_writer_epoch
        self.plan_hash = writer.plan_hash
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        # No state to release — the locked-append helper owns its own flock
        # for each call; this context just gates entry and carries captured
        # epoch into append() invocations.
        return None

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        """Append ``event`` via :func:`append_event_locked`.

        Reads the tail freshly inside the locked-append call (under flock)
        and CAS-checks both tail and epoch atomically. A takeover between
        ``__enter__`` and this call surfaces as :class:`StaleEpochError`
        from :func:`append_event_locked`.
        """

        if self.run_dir is None:
            raise RuntimeError("WriterContext.append called outside of `with` block")
        # The tail CAS in append_event_locked re-reads under the flock; we
        # supply the current tail by reading it (unlocked) immediately
        # prior. If a concurrent appender slipped in, the under-lock tail
        # will differ and StaleTailError fires — exactly the apex contract.
        from astrid.core.task.events import _peek_tail_hash  # local import

        expected_prev = _peek_tail_hash(self.run_dir / "events.jsonl")
        return append_event_locked(
            self.run_dir,
            event,
            expected_writer_epoch=self.expected_writer_epoch,
            expected_prev_hash=expected_prev,
        )


def writer_context_from_decision(
    decision: _HasSession,
    *,
    root: str | Path | None = None,
    session_root: str | Path | None = None,
) -> WriterContext:
    """Factory used by post-dispatch ``record_*`` helpers.

    Accepts any object exposing ``.session: Session`` — including the
    extended ``GateDecision`` T8/T9 introduce. Performs the same
    writer-auth check on ``__enter__`` as :class:`WriterContext`.
    """

    return WriterContext(decision.session, root=root, session_root=session_root)
