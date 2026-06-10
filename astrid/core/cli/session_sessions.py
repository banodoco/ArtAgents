"""Session CLI sessions subcommand handlers: ls, detach, takeover, prune.

Extracted from ``astrid.core.session.cli`` during M4 giant-file decomposition.
The ``cmd_sessions_*`` functions live here; shared helpers (``_list_session_files``,
``_session_store``, ``_ensure_identity``, ``_find_reusable_session``,
``_make_bootstrap_session``, ``NONE_PLACEHOLDER``) are imported at module level
from ``._shared`` (no facade cycle).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.foundation.project_paths import project_dir, resolve_projects_root
from astrid.core.project.current_run import read_current_run
from astrid.core.project.project import ProjectError, require_project
from astrid.core.session._shared import (
    NONE_PLACEHOLDER,
    _ensure_identity,
    _find_reusable_session,
    _make_bootstrap_session,
    _session_store,
)
from astrid.core.session.binding import (
    SessionBindingError,
    resolve_current_session,
)
from astrid.core.session.discovery import discover_projects
from astrid.core.session.identity import IdentityError
from astrid.core.session.lease import (
    LeaseError,
    read_lease,
)
from astrid.core.session.lifecycle import (
    SessionTakeoverTargetError,
    takeover_session,
)
from astrid.core.session.model import (
    Session,
    SessionRecordNotFoundError,
    SessionRole,
    SessionStoreError,
)
from astrid.core.session.paths import (
    session_path,
    sessions_dir,
)
from astrid.core.task.events import EVENTS_FILENAME

# NOTE: ``_list_session_files`` is a pinned monkeypatch seam (the contract
# patches ``session_cli._list_session_files``). The two ``cmd_sessions_*``
# handlers below resolve it through the ``.cli`` facade at call time so that
# seam keeps working — this is the same deliberate indirection used for
# ``attach_session`` and the ``cmd_*`` handlers, NOT the shared-helper cycle.
from astrid.core.timeline.defaults import read_project_default
from astrid.core.timeline.paths import find_timeline_slug_for_ulid
from astrid.core.util.time import utc_now_iso

# ----- cmd_sessions_ls --------------------------------------------------


def cmd_sessions_ls(args: argparse.Namespace, *, out: Any = None) -> int:
    # _list_session_files resolved through the facade — pinned monkeypatch seam.
    from astrid.core.cli.session import _list_session_files  # noqa: PLC0415

    if out is None:
        out = sys.stdout
    sessions = _list_session_files()
    if not sessions:
        print("no sessions", file=out)
        return 0
    for s in sessions:
        timeline_display = s.timeline
        if timeline_display is None and s.timeline_id is not None:
            timeline_display = find_timeline_slug_for_ulid(
                s.project, s.timeline_id
            )
        print(
            f"{s.id}  project={s.project}  "
            f"timeline={timeline_display or NONE_PLACEHOLDER}  "
            f"run={s.run_id or NONE_PLACEHOLDER}  last_used={s.last_used_at}",
            file=out,
        )
    return 0


# ----- cmd_sessions_detach ----------------------------------------------


def cmd_sessions_detach(args: argparse.Namespace, *, out: Any = None) -> int:
    from astrid.core.session.binding import ASTRID_SESSION_ID_ENV

    if out is None:
        out = sys.stdout
    target = args.session_id
    if not target:
        env_id = sys.modules["os"].environ.get(ASTRID_SESSION_ID_ENV)
        if not env_id:
            raise AstridError(
                "detach: no session bound (ASTRID_SESSION_ID unset); pass a session id",
                recovery_command="astrid sessions ls",
            )
        target = env_id
    try:
        _session_store().delete(target)
    except SessionRecordNotFoundError:
        raise AstridError(
            f"detach: no session file for id {target!r}",
            recovery_command="astrid sessions ls",
            state_snapshot={"session_id": target},
        )
    print(f"detached {target}", file=out)
    return 0


# ----- cmd_sessions_takeover --------------------------------------------


def _raise_takeover_status_recovery(reason: str) -> None:
    raise AstridError(
        f"takeover: {reason}",
        recovery_command="astrid status",
    )


def _resolve_unbound_takeover_target(target: str) -> tuple[str, str, Path, str | None] | None:
    target_path = session_path(target)
    if target_path.exists():
        target_sess = Session.from_json(target_path)
        if target_sess.run_id is None:
            _raise_takeover_status_recovery(
                f"target session {target!r} is not bound to a run"
            )
            return None
        run_dir = project_dir(target_sess.project) / "runs" / target_sess.run_id
        if not (run_dir / EVENTS_FILENAME).exists():
            _raise_takeover_status_recovery(
                f"target session {target!r} points at missing run "
                f"{target_sess.run_id!r} in project {target_sess.project!r}"
            )
            return None
        return target_sess.project, target_sess.run_id, run_dir, target_sess.id

    matches: list[tuple[str, Path]] = []
    for slug in discover_projects():
        candidate = project_dir(slug) / "runs" / target
        if (candidate / EVENTS_FILENAME).exists():
            matches.append((slug, candidate))
    if not matches:
        _raise_takeover_status_recovery(
            f"{target!r} matches neither a session id nor a discovered run id"
        )
        return None
    if len(matches) > 1:
        projects = ", ".join(slug for slug, _ in matches)
        _raise_takeover_status_recovery(
            f"run id {target!r} is ambiguous across projects: {projects}"
        )
        return None
    slug, run_dir = matches[0]
    return slug, target, run_dir, None


def _build_takeover_session(
    slug: str,
    run_id: str,
    *,
    role: SessionRole,
    out: Any,
) -> Session | None:
    try:
        identity = _ensure_identity(out=out)
        require_project(slug)
    except (IdentityError, ProjectError) as exc:
        raise AstridError(f"takeover: {exc}", recovery_command="astrid status") from exc

    now = utc_now_iso()
    reusable = _find_reusable_session(slug, identity.agent_id)
    if reusable is not None:
        session = reusable.with_changes(
            run_id=run_id,
            role=role,
            last_used_at=now,
        )
    else:
        timeline_id = read_project_default(slug)
        timeline_slug = (
            find_timeline_slug_for_ulid(slug, timeline_id)
            if timeline_id is not None
            else None
        )
        session = _make_bootstrap_session(
            slug=slug,
            agent_id=identity.agent_id,
            role=role,
            run_id=run_id,
            timeline_slug=timeline_slug,
            timeline_id=timeline_id,
            now=now,
        )
    return session


def cmd_sessions_takeover(args: argparse.Namespace, *, out: Any = None) -> int:
    if out is None:
        out = sys.stdout
    projects_root = resolve_projects_root()
    session_root = sessions_dir()
    try:
        # T9 / FLAG-S1-003: INTENTIONALLY env-only (no slug=). This verb
        # diagnoses env-binding by surface; masking the env with a file
        # fallback would defeat its purpose.
        current = resolve_current_session()
    except SessionBindingError as exc:
        raise AstridError(f"takeover: {exc}", recovery_command="astrid status") from exc
    bootstrapped_unbound = False
    if current is None:
        resolved = _resolve_unbound_takeover_target(args.target)
        if resolved is None:
            return 2
        slug, run_id, target_run_dir, _prev_session_id = resolved
        try:
            lease = read_lease(target_run_dir)
        except LeaseError as exc:
            raise AstridError(
                f"takeover: cannot read canonical lease for {target_run_dir.name!r}: {exc}",
                recovery_command="astrid status",
                state_snapshot={"run_id": target_run_dir.name},
            )
        role: SessionRole = (
            "orphan-pending"
            if lease.get("attached_session_id") is None
            else "reader"
        )
        current = _build_takeover_session(
            slug,
            run_id,
            role=role,
            out=out,
        )
        if current is None:
            return 2
        bootstrapped_unbound = True

    try:
        result = takeover_session(
            caller_session=current,
            target=args.target if not bootstrapped_unbound else run_id,
            projects_root=projects_root,
            session_root=session_root,
            force=args.force,
            reason="cli-takeover",
            write_project_pointer=bootstrapped_unbound,
        )
    except SessionTakeoverTargetError as exc:
        if "matches neither" in str(exc):
            cause = f"takeover: {exc}"
        elif not bootstrapped_unbound:
            cause = (
                f"takeover: {args.target!r} matches neither a session id nor a run id "
                f"in project {current.project!r}"
            )
        else:
            cause = f"takeover: {exc}"
        raise AstridError(
            cause,
            recovery_command="astrid status",
            state_snapshot={"target": args.target, "project": current.project},
        ) from exc
    except LeaseError as exc:
        msg = str(exc)
        if "missing lease" in msg or "invalid JSON" in msg:
            cause = (
                f"takeover: cannot read canonical lease for {args.target!r}: {exc}"
            )
        else:
            cause = f"takeover: {exc}"
        raise AstridError(
            cause,
            recovery_command="astrid status",
            state_snapshot={"target": args.target},
        ) from exc

    updated = result.lease
    if result.operation == "orphan-claim":
        print(
            f"claimed orphan lease; writer_epoch={updated['writer_epoch']}, "
            f"writer={updated['attached_session_id']}",
            file=out,
        )
        return 0
    print(
        f"took over; writer_epoch={updated['writer_epoch']}, "
        f"writer={updated['attached_session_id']}",
        file=out,
    )
    return 0


# ----- cmd_sessions_prune -----------------------------------------------


def cmd_sessions_prune(args: argparse.Namespace, *, out: Any = None) -> int:
    """Prune stale session records.

    Defaults to dry-run: lists candidates without deleting anything.
    Pass ``--apply`` to actually remove the listed session files.

    A session is considered stale when its ``last_used_at`` is older than
    ``--older-than-days`` (default 30) relative to the current UTC time.
    """
    # _list_session_files resolved through the facade — pinned monkeypatch seam.
    from astrid.core.cli.session import _list_session_files  # noqa: PLC0415

    if out is None:
        out = sys.stdout
    try:
        from datetime import datetime, timedelta
        from datetime import timezone as dt_timezone

        now = datetime.now(dt_timezone.utc)
        cutoff = now - timedelta(days=args.older_than_days)
    except Exception as exc:
        raise AstridError(
            "prune: unable to compute cutoff",
            recovery_command="astrid sessions prune --older-than-days <days>",
            state_snapshot={"older_than_days": getattr(args, "older_than_days", None)},
        ) from exc

    all_sessions = _list_session_files()
    if not all_sessions:
        print("no session records found", file=out)
        return 0

    stale: list[tuple[Session, float, Path]] = []
    for s in all_sessions:
        spath = _session_store().session_path(s.id)
        try:
            last_used = datetime.fromisoformat(s.last_used_at)
        except (ValueError, TypeError):
            # Unparseable timestamp — treat as stale for safety.
            stale.append((s, float("inf"), spath))
            continue
        age_days = (now - last_used).total_seconds() / 86400.0
        if last_used < cutoff:
            stale.append((s, age_days, spath))

    if not stale:
        print(
            f"no stale sessions found (cutoff: >{args.older_than_days} days)",
            file=out,
        )
        return 0

    # Stable sort: oldest first (largest age_days).
    stale.sort(key=lambda t: t[1], reverse=True)

    dry_run = not args.apply
    header = "[DRY RUN] " if dry_run else ""
    print(
        f"{header}{len(stale)} stale session(s) older than "
        f"{args.older_than_days} days",
        file=out,
    )
    print(file=out)

    for s, age_days, spath in stale:
        age_str = f"{age_days:.1f}d" if age_days != float("inf") else "?"
        action = "would delete" if dry_run else "deleting"
        print(
            f"  {action} {s.id}  project={s.project}  "
            f"age={age_str}  path={spath}",
            file=out,
        )

    if dry_run:
        print(file=out)
        print("Dry run — no sessions were deleted.", file=out)
        print("Re-run with --apply to delete the listed sessions.", file=out)
        return 0

    # Apply mode: actually delete.
    deleted = 0
    errors: list[dict[str, str]] = []
    for s, age_days, spath in stale:
        try:
            _session_store().delete(s.id)
            deleted += 1
        except (OSError, SessionStoreError) as exc:
            errors.append({"session_id": s.id, "path": str(spath), "error": str(exc)})

    print(file=out)
    print(f"deleted {deleted} session record(s).", file=out)
    if errors:
        print(f"{len(errors)} error(s) encountered.", file=out)
        raise AstridError(
            "prune: failed to delete one or more stale sessions",
            recovery_command="astrid sessions prune --apply",
            state_snapshot={
                "deleted": deleted,
                "errors": errors,
            },
        )
    return 0
