"""Session CLI verbs: attach, status, sessions ls/detach/takeover.

The CLI gate (T8) routes everything outside the unbound allowlist into
``cmd_status`` / ``cmd_attach`` first so a fresh tab without a session
gets a structured prompt rather than an opaque error.

Takeover bootstrap contract: unbound ``astrid sessions takeover`` is an
allowed entrypoint only when it first creates or selects a concrete caller
session through the same identity/session path as ``attach``, persists that
session, binds the tab, and then performs the lease takeover atomically. It
must fail without mutation and point at ``astrid status`` when it cannot safely
choose the project/run. Anonymous takeover is never valid.

Output formats use literal template strings so tests can string-match.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from astrid.contracts.errors import AstridError
from astrid.core.project.current_run import read_current_run
from astrid.core.project.paths import project_dir, resolve_projects_root
from astrid.core.project.project import ProjectError, require_project
from astrid.core.session.binding import (
    ASTRID_SESSION_ID_ENV,
    SESSION_FILE_NAME,
    SessionBindingError,
    attach_session,
    resolve_current_session,
)
from astrid.core.session.config import resolve_default_project, set_default_project
from astrid.core.session.constants import STUCK_NO_EVENT_SECONDS
from astrid.core.session.discovery import discover_projects
from astrid.core.session.identity import (
    Identity,
    IdentityError,
    bootstrap_identity,
    read_identity,
    validate_agent_slug,
)
from astrid.core.session.lease import (
    LeaseError,
    read_lease,
)
from astrid.core.session.lifecycle import (
    SessionTakeoverTargetError,
    load_session,
    takeover_session,
)
from astrid.core.session.model import (
    Session,
    SessionRecordNotFoundError,
    SessionRole,
    SessionStore,
)
from astrid.core.session.paths import (
    session_path,
    sessions_dir,
)
from astrid.core.task.events import EVENTS_FILENAME, read_events
from astrid.core.timeline import crud as timeline_crud
from astrid.core.timeline.defaults import read_project_default
from astrid.core.timeline.paths import find_timeline_by_slug, find_timeline_slug_for_ulid
from astrid.core.util.log_and_swallow import log_and_swallow
from astrid.core.util.time import utc_now_iso
from astrid.threads.ids import generate_ulid

# ----- Templates --------------------------------------------------------
#
# Tests assert on these literal strings; keep them stable.

ATTACH_HEADER = "session created"
ATTACH_HEADER_REUSED = "session reused (idempotent re-attach)"
EXPORT_LINE_TEMPLATE = "export ASTRID_SESSION_ID={sid}"
TAKEOVER_HINT_READER = "another session ({writer}) holds this run; take over with: astrid sessions takeover {run_id}"
TAKEOVER_HINT_ORPHAN = "lease is orphan-pending; claim it with: astrid sessions takeover {run_id}"
STATUS_UNBOUND_HEADER = "no session bound"
ATTACH_SUGGESTION_TEMPLATE = "  astrid attach {slug}"
NO_PROJECTS_FOUND = "no projects discovered under the projects root"
FIRST_RUN_PROMPT_HEADER = "first-run bootstrap: no agent identity on this machine"

NONE_PLACEHOLDER = "(none)"


# ----- Helpers ----------------------------------------------------------
def _parse_agent_override(raw: str) -> str:
    """Parse ``agent:<slug>`` from ``--as`` argument; raise on malformed."""

    if not raw.startswith("agent:"):
        raise AstridError(
            f"attach: --as must be of form 'agent:<slug>', got {raw!r}",
            recovery_command="astrid attach <project> --as agent:<slug>",
        )
    return validate_agent_slug(raw[len("agent:") :])


def _ensure_identity(*, prompt: Any = None, out: Any = None) -> Identity:
    """Return the on-disk identity, triggering first-run bootstrap if absent.

    ``prompt`` is forwarded to :func:`bootstrap_identity`; ``None`` lets
    that helper resolve :func:`builtins.input` lazily.
    """

    if out is None:
        out = sys.stdout
    existing = read_identity()
    if existing is not None:
        return existing
    print(FIRST_RUN_PROMPT_HEADER, file=out)
    return bootstrap_identity(prompt=prompt)


def _list_session_files() -> list[Session]:
    return _session_store().iter_sessions(skip_malformed=True)


def _session_store() -> SessionStore:
    return SessionStore(session_root=sessions_dir())


def _find_reusable_session(slug: str, agent_id: str) -> Session | None:
    """Find a prior session for ``(slug, agent_id)`` that's safe to reuse.

    Reuse is the idempotency primitive for `astrid attach` (#19/#23). The v3
    DS probe found that 4/5 agents hit the "new shell → attach → reader → ...
    → takeover --force" dance every time they reconnected. v4's idem probe
    found the initial fix (#19) was a no-op under realistic conditions
    because the warmth check fired BEFORE the lease-ownership check — and an
    actively-acking agent leaves the run permanently warm. The actor was
    treated as a stranger every time.

    Reordered decision (#23):

      1. If there's no active run → any matching session is reusable.
      2. If the lease is held by one of OUR candidate sessions → reuse it.
         This is the agent reconnecting to their own active work. Warmth is
         not a concern — they ARE the warm writer.
      3. If the lease is orphan (no holder): reuse most-recent IF not warm.
         A warm orphan means someone is mid-write without a lease record
         (rare but unsafe to steal).
      4. If the lease is held by a different actor: do NOT reuse. Caller
         falls through to fresh-session and (if applicable) takeover.

    Returns the most-recently-used reusable session, or None.
    """
    candidates = [
        s for s in _list_session_files()
        if s.project == slug and s.agent_id == agent_id
    ]
    if not candidates:
        return None
    candidate_ids = {s.id for s in candidates}
    on_disk_run_id = read_current_run(slug)
    if on_disk_run_id is None:
        # No active run — any matching session is reusable; pick most recent.
        return sorted(candidates, key=lambda s: s.last_used_at or "", reverse=True)[0]
    run_dir = project_dir(slug) / "runs" / on_disk_run_id
    lease = read_lease(run_dir)
    attached = lease.get("attached_session_id")
    # (2) Lease held by us → always reuse. Don't gate on warmth: the actor's
    # own recent writes are why the run is warm.
    if isinstance(attached, str) and attached in candidate_ids:
        for s in candidates:
            if s.id == attached:
                return s
    # (3) Orphan lease → safe to reuse only if the run isn't warm. A warm
    # orphan is the rare case where some process is writing without holding
    # the lease record; better to fail closed and let `--fresh` resolve it.
    if attached is None:
        if _is_target_warm(run_dir):
            return None
        return sorted(candidates, key=lambda s: s.last_used_at or "", reverse=True)[0]
    # (4) Lease held by a different actor → defer to takeover flow.
    return None


def _write_session_pointer(slug: str, session_id: str) -> None:
    session_file = project_dir(slug) / SESSION_FILE_NAME
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        f"{ASTRID_SESSION_ID_ENV}={session_id}\n", encoding="utf-8"
    )
    try:
        session_file.chmod(0o600)
    except OSError:
        pass


def _make_bootstrap_session(
    *,
    slug: str,
    agent_id: str,
    role: SessionRole,
    run_id: str | None,
    timeline_slug: str | None,
    timeline_id: str | None,
    now: str,
) -> Session:
    return Session(
        id=generate_ulid(),
        project=slug,
        timeline=timeline_slug,
        timeline_id=timeline_id,
        run_id=run_id,
        agent_id=agent_id,
        attached_at=now,
        last_used_at=now,
        role=role,
    )


def _last_event_ts(run_dir: Path) -> str | None:
    events_path = run_dir / EVENTS_FILENAME
    if not events_path.exists() or events_path.stat().st_size == 0:
        return None
    events = read_events(events_path)
    if not events:
        return None
    ts = events[-1].get("ts")
    return ts if isinstance(ts, str) else None


def _is_target_warm(run_dir: Path) -> bool:
    """A target run is 'warm' if its events.jsonl was modified within
    STUCK_NO_EVENT_SECONDS of now. Warm targets require --force to take
    over. We use file mtime rather than parsed event ts so the check
    works whether or not the event carries a timestamp field.
    """

    events_path = run_dir / EVENTS_FILENAME
    if not events_path.exists() or events_path.stat().st_size == 0:
        return False
    age = time.time() - events_path.stat().st_mtime
    return age < STUCK_NO_EVENT_SECONDS


# ----- cmd_attach -------------------------------------------------------


def cmd_attach(args: argparse.Namespace, *, out: Any = None) -> int:
    if out is None:
        out = sys.stdout
    projects_root = resolve_projects_root()
    session_root = sessions_dir()
    try:
        identity = _ensure_identity(out=out)
    except IdentityError as exc:
        raise AstridError(f"attach: {exc}", recovery_command="astrid status") from exc
    agent_id = identity.agent_id
    if args.as_agent:
        try:
            agent_id = _parse_agent_override(args.as_agent)
        except (ValueError, IdentityError) as exc:
            raise AstridError(
                f"attach: {exc}",
                recovery_command="astrid attach <project> --as agent:<slug>",
            ) from exc

    if args.session:
        # Resume an existing session by id; the env var still has to be
        # exported by the operator after this call.
        try:
            stored = load_session(args.session, session_root=session_root)
        except SessionRecordNotFoundError:
            raise AstridError(
                f"attach: no session file for id {args.session!r}",
                recovery_command="astrid sessions ls",
                state_snapshot={"session_id": args.session},
            )
        session = attach_session(
            project_slug=stored.project,
            agent_id=stored.agent_id,
            projects_root=projects_root,
            session_root=session_root,
            session_id=stored.id,
            opened_at=utc_now_iso(),
            write_project_pointer=True,
        ).session
        sid = session.id
        slug = session.project
        # Resumed sessions: use the stored timeline info; do NOT backfill.
        resolved_timeline_slug = session.timeline
        resolved_timeline_id = session.timeline_id
    else:
        explicit_project = args.project is not None
        slug = args.project or resolve_default_project()
        if not slug:
            projects = discover_projects()
            recovery = (
                f"astrid attach {projects[0]}"
                if projects
                else "astrid projects create <slug>"
            )
            raise AstridError(
                "attach: no project specified and no default project configured",
                valid_options=projects,
                recovery_command=recovery,
                state_snapshot={"projects": projects},
            )
        try:
            require_project(slug)
        except ProjectError:
            projects = discover_projects()
            if args.project:
                cause = f"attach: project '{slug}' was not found under the current projects root"
                recovery = (
                    f"astrid attach {projects[0]}"
                    if projects
                    else "astrid projects create <slug>"
                )
            else:
                cause = (
                    f"attach: configured default project '{slug}' was not found "
                    "under the current projects root"
                )
                recovery = (
                    f"astrid projects default {projects[0]}"
                    if projects
                    else "astrid projects create <slug>"
                )
            raise AstridError(
                cause,
                valid_options=projects,
                recovery_command=recovery,
                state_snapshot={"project": slug, "projects": projects},
            )
        # Idempotency (#19): reuse a prior session for (slug, agent_id) when
        # safe, skipping the timeline-resolution / new-session branch entirely.
        # Killing the new-shell → reader → takeover dance was the dominant ask
        # from the v3 DS probe (4/5 reports).
        _reusable = (
            None
            if getattr(args, "fresh", False)
            else _find_reusable_session(slug, agent_id)
        )
        if _reusable is not None:
            refreshed = attach_session(
                project_slug=slug,
                agent_id=agent_id,
                projects_root=projects_root,
                session_root=session_root,
                session_id=_reusable.id,
                opened_at=utc_now_iso(),
                write_project_pointer=True,
            ).session
            print(ATTACH_HEADER_REUSED, file=out)
            print(f"export ASTRID_SESSION_ID={refreshed.id}", file=out)
            print(f"project: {refreshed.project}", file=out)
            print(f"timeline: {refreshed.timeline or NONE_PLACEHOLDER}", file=out)
            print(f"run: {refreshed.run_id or NONE_PLACEHOLDER}", file=out)
            print(f"role: {refreshed.role}", file=out)
            return 0

        # Resolve timeline: explicit flag → project default → prompt / error.
        resolved_timeline_id: str | None = None
        if args.timeline:
            found = find_timeline_by_slug(slug, args.timeline)
            if found is None:
                from astrid.core.timeline.crud import list_timelines

                available = [timeline.slug for timeline in list_timelines(slug)]
                raise AstridError(
                    f"attach: timeline '{args.timeline}' not found in project '{slug}'",
                    valid_options=available,
                    recovery_command=f"astrid attach {slug} --timeline <slug>",
                    state_snapshot={"project": slug, "timeline": args.timeline},
                )
            resolved_timeline_id = found[0]
            resolved_timeline_slug = args.timeline
        else:
            default_ulid = read_project_default(slug)
            if default_ulid is not None:
                default_slug = find_timeline_slug_for_ulid(slug, default_ulid)
                if default_slug is not None:
                    resolved_timeline_id = default_ulid
                    resolved_timeline_slug = default_slug
                    print(
                        f"Using default timeline: {default_slug}. "
                        f"Use --timeline to override.",
                        file=out,
                    )
                else:
                    resolved_timeline_slug = None
            else:
                resolved_timeline_slug = None

            if resolved_timeline_id is None:
                # No explicit flag, no default → prompt or error.
                from astrid.core.timeline.crud import list_timelines

                available = list_timelines(slug)
                if not available:
                    # Bootstrap case: no timelines at all.  Proceed without one;
                    # the user can create timelines once attached.
                    print(
                        f"attach: no timelines exist for project '{slug}' yet; "
                        "session bound without a timeline. "
                        "Run `astrid timelines create <slug>` to make one.",
                        file=out,
                    )
                    resolved_timeline_slug = None
                elif sys.stdin.isatty():
                    print("Available timelines:", file=out)
                    for t in available:
                        print(f"  {t.slug}  ({t.name})", file=out)
                    try:
                        choice = input("Choose a timeline slug: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        raise AstridError(
                            "attach: cancelled",
                            recovery_command=f"astrid attach {slug} --timeline <slug>",
                        )
                    found = find_timeline_by_slug(slug, choice)
                    if found is None:
                        raise AstridError(
                            f"attach: timeline '{choice}' not found",
                            valid_options=[t.slug for t in available],
                            recovery_command=f"astrid attach {slug} --timeline <slug>",
                            state_snapshot={"project": slug, "timeline": choice},
                        )
                    resolved_timeline_id = found[0]
                    resolved_timeline_slug = choice
                else:
                    raise AstridError(
                        "no default timeline; pass --timeline <slug>",
                        valid_options=[t.slug for t in available],
                        recovery_command=f"astrid attach {slug} --timeline <slug>",
                        state_snapshot={"project": slug},
                    )
        session = attach_session(
            project_slug=slug,
            agent_id=agent_id,
            projects_root=projects_root,
            session_root=session_root,
            timeline=resolved_timeline_slug,
            timeline_id=resolved_timeline_id,
            attached_at=utc_now_iso(),
            write_project_pointer=True,
        ).session
        sid = session.id
        if getattr(args, "set_default", False):
            set_default_project(
                slug,
                scope="user" if getattr(args, "user_default", False) else "workspace",
            )

    # Determine the current role/hint from the active run the lifecycle helper
    # just bound against, while keeping the stable CLI output strings.
    on_disk_run_id = session.run_id
    role: SessionRole = session.role
    takeover_hint: str | None = None
    if on_disk_run_id is not None:
        run_dir = project_dir(slug) / "runs" / on_disk_run_id
        lease = read_lease(run_dir)
        attached = lease.get("attached_session_id")
        if attached is None:
            takeover_hint = TAKEOVER_HINT_ORPHAN.format(run_id=on_disk_run_id)
        elif attached != sid:
            takeover_hint = TAKEOVER_HINT_READER.format(
                writer=attached, run_id=on_disk_run_id
            )

    print(ATTACH_HEADER, file=out)
    if not args.session and getattr(args, "set_default", False):
        scope = "user" if getattr(args, "user_default", False) else "workspace"
        label = "saved default project" if explicit_project else "using default project"
        print(f"{label} ({scope}): {slug}", file=out)
    print(EXPORT_LINE_TEMPLATE.format(sid=sid), file=out)
    print(f"project: {slug}", file=out)
    print(f"timeline: {resolved_timeline_slug or NONE_PLACEHOLDER}", file=out)
    print(f"run: {on_disk_run_id or NONE_PLACEHOLDER}", file=out)
    print(f"role: {role}", file=out)
    if takeover_hint is not None:
        print(takeover_hint, file=out)
    return 0


# ----- cmd_sessions_ls --------------------------------------------------


def cmd_sessions_ls(args: argparse.Namespace, *, out: Any = None) -> int:
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


# ----- cmd_status -------------------------------------------------------


def cmd_status(args: argparse.Namespace, *, out: Any = None) -> int:
    if out is None:
        out = sys.stdout
    try:
        # T9 / FLAG-S1-003: INTENTIONALLY env-only (no slug=). `session
        # status` reports on the live env binding; pulling a file fallback
        # would mask the unbound-state it exists to surface.
        session = resolve_current_session()
    except SessionBindingError as exc:
        raise AstridError(f"status: {exc}", recovery_command="astrid status") from exc

    if session is None:
        return _render_unbound_status(out=out)
    return _render_bound_status(session, out=out)


def _render_unbound_status(*, out: Any) -> int:
    print(STATUS_UNBOUND_HEADER, file=out)
    default = resolve_default_project()
    projects = discover_projects()
    default_is_available = bool(default and default in projects)
    if default_is_available:
        print(f"default project: {default}", file=out)
    elif default:
        print(f"configured default project: {default} (not found under current projects root)", file=out)
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


def _print_discovery_hints(*, out: Any) -> None:
    print("  astrid skills list          # discover pack skills and install state", file=out)
    print("  astrid orchestrators list   # discover workflows", file=out)
    print("  astrid executors list       # discover concrete tools", file=out)
    print("  astrid elements list        # discover render building blocks", file=out)


def _render_bound_status(session: Session, *, out: Any) -> int:
    # Fix 2 (v6 dogfood): the per-tab `--as agent:<slug>` override is
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
        from astrid.core.timeline.defaults import read_project_default

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
        timeline_line += f" ({timeline_final_count} final output{'s' if timeline_final_count != 1 else ''})"

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
        print(f"  astrid next --project {session.project}   # continue current task run", file=out)
    else:
        print(f"  astrid start <orchestrator-id> --project {session.project}   # start a task list", file=out)
    print("", file=out)
    print("discover:", file=out)
    _print_discovery_hints(out=out)
    return 0


# ----- argparse glue ----------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m astrid sessions")
    sub = parser.add_subparsers(dest="command", required=True)

    attach = sub.add_parser("attach", help="Bind the current tab to a project.")
    attach.add_argument("project", nargs="?")
    attach.add_argument("--timeline")
    attach.add_argument("--session", help="Resume an existing session id.")
    attach.add_argument("--as", dest="as_agent", help="Per-tab agent override (agent:<slug>).")
    attach.add_argument(
        "--default",
        action="store_true",
        dest="set_default",
        help="Remember this project as the workspace default.",
    )
    attach.add_argument(
        "--user",
        action="store_true",
        dest="user_default",
        help="With --default, write the user-wide default instead of the workspace default.",
    )
    attach.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "Force a new session id even when a reusable session exists for "
            "this (project, agent) pair. By default attach is idempotent and "
            "reuses prior sessions; --fresh opts out."
        ),
    )
    attach.set_defaults(handler=cmd_attach)

    ls = sub.add_parser("ls", aliases=["list"], help="List sessions in ~/.astrid/sessions/.")
    ls.set_defaults(handler=cmd_sessions_ls)

    detach = sub.add_parser("detach", help="Detach a session (defaults to current tab).")
    detach.add_argument("session_id", nargs="?")
    detach.set_defaults(handler=cmd_sessions_detach)

    takeover = sub.add_parser("takeover", help="Take over a run lease.")
    takeover.add_argument("target", help="Session id or run id.")
    takeover.add_argument("--force", action="store_true", help="Allow takeover of a warm target.")
    takeover.set_defaults(handler=cmd_sessions_takeover)

    status = sub.add_parser("status", help="Print the current session breadcrumb.")
    status.set_defaults(handler=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
