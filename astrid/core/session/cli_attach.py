"""Session CLI attach command and helpers.

Extracted from ``astrid.core.session.cli`` during M4 giant-file decomposition.
The ``cmd_attach`` function and its file-local helpers live here; shared helpers
(``_ensure_identity``, ``_find_reusable_session``, ``_json_mode``,
``_emit_notice``) are imported from ``.cli`` via late imports inside functions
to preserve monkeypatch seams.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from astrid.contracts.errors import AstridError
from astrid.core.project.current_run import read_current_run
from astrid.core.project.paths import project_dir, resolve_projects_root
from astrid.core.project.project import ProjectError, require_project
# attach_session is imported via late import inside cmd_attach to preserve
# monkeypatch seams (tests setattr on cli.attach_session).
from astrid.core.session.config import resolve_default_project, set_default_project
from astrid.core.session.discovery import discover_projects
from astrid.core.session.identity import (
    IdentityError,
    validate_agent_slug,
)
from astrid.core.session.lease import read_lease
from astrid.core.session.model import (
    SessionRecordNotFoundError,
    SessionRole,
)
from astrid.core.session.paths import sessions_dir
from astrid.core.task.cli_contract import emit_lifecycle_json
from astrid.core.timeline.crud import list_timelines
from astrid.core.timeline.defaults import read_project_default
from astrid.core.timeline.paths import find_timeline_by_slug, find_timeline_slug_for_ulid
from astrid.core.util.time import utc_now_iso

# ----- Templates --------------------------------------------------------
#
# Tests assert on these literal strings; keep them stable.

ATTACH_HEADER = "session created"
ATTACH_HEADER_REUSED = "session reused (idempotent re-attach)"
EXPORT_LINE_TEMPLATE = "export ASTRID_SESSION_ID={sid}"
# ----- Helpers ----------------------------------------------------------

def _parse_agent_override(raw: str) -> str:
    """Parse ``agent:<slug>`` from ``--as`` argument; raise on malformed."""

    if not raw.startswith("agent:"):
        raise AstridError(
            f"attach: --as must be of form 'agent:<slug>', got {raw!r}",
            recovery_command="astrid attach <project> --as agent:<slug>",
        )
    return validate_agent_slug(raw[len("agent:"):])


def _emit_attach_json(
    *,
    project: str,
    run_id: str | None,
    session_id: str,
    agent_id: str,
    timeline: str | None,
    role: SessionRole,
    attach_kind: str,
    out: Any,
) -> int:
    return emit_lifecycle_json(
        project=project,
        run_id=run_id,
        state="attached",
        stream=out,
        session_id=session_id,
        agent_id=agent_id,
        timeline=timeline,
        role=role,
        export_line=EXPORT_LINE_TEMPLATE.format(sid=session_id),
        attach_kind=attach_kind,
    )


# ----- cmd_attach -------------------------------------------------------


def cmd_attach(args: argparse.Namespace, *, out: Any = None) -> int:
    # Late imports from .cli to preserve monkeypatch seams.
    # attach_session is imported here (not at top level) so that
    # monkeypatch.setattr(cli, "attach_session", ...) routes through
    # the cli facade — tests spy on cli.attach_session.
    from astrid.core.session.cli import (  # noqa: PLC0415
        NONE_PLACEHOLDER,
        TAKEOVER_HINT_ORPHAN,
        TAKEOVER_HINT_READER,
        _emit_notice,
        _ensure_identity,
        _find_reusable_session,
        _json_mode,
        attach_session,
    )

    if out is None:
        out = sys.stdout
    json_mode = _json_mode(args)
    projects_root = resolve_projects_root()
    session_root = sessions_dir()
    try:
        identity = _ensure_identity(out=out, allow_prompt=not json_mode)
    except IdentityError as exc:
        project_hint = getattr(args, "project", None) or "<project>"
        raise AstridError(
            f"attach: {exc}",
            recovery_command=f"astrid attach {project_hint}",
        ) from exc
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
        from astrid.core.session.lifecycle import load_session  # noqa: PLC0415

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
        attach_kind = "resumed"
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
            if json_mode:
                return _emit_attach_json(
                    project=refreshed.project,
                    run_id=refreshed.run_id,
                    session_id=refreshed.id,
                    agent_id=refreshed.agent_id,
                    timeline=refreshed.timeline,
                    role=refreshed.role,
                    attach_kind="reused",
                    out=out,
                )
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
                    _emit_notice(
                        f"Using default timeline: {default_slug}. "
                        f"Use --timeline to override.",
                        json_mode=json_mode,
                        out=out,
                    )
                else:
                    resolved_timeline_slug = None
            else:
                resolved_timeline_slug = None

            if resolved_timeline_id is None:
                # No explicit flag, no default → prompt or error.
                available = list_timelines(slug)
                if not available:
                    # Bootstrap case: no timelines at all.  Proceed without one;
                    # the user can create timelines once attached.
                    _emit_notice(
                        f"attach: no timelines exist for project '{slug}' yet; "
                        "session bound without a timeline. "
                        "Run `astrid timelines create <slug>` to make one.",
                        json_mode=json_mode,
                        out=out,
                    )
                    resolved_timeline_slug = None
                elif json_mode:
                    raise AstridError(
                        "attach: no default timeline; pass --timeline <slug>",
                        valid_options=[t.slug for t in available],
                        recovery_command=f"astrid attach {slug} --timeline <slug>",
                        state_snapshot={"project": slug},
                    )
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
        attach_kind = "fresh"
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

    if json_mode:
        return _emit_attach_json(
            project=slug,
            run_id=on_disk_run_id,
            session_id=sid,
            agent_id=session.agent_id,
            timeline=resolved_timeline_slug,
            role=role,
            attach_kind=attach_kind,
            out=out,
        )
    print(ATTACH_HEADER, file=out)
    if not args.session and getattr(args, "set_default", False):
        scope = "user" if getattr(args, "user_default", False) else "workspace"
        label = "saved default project" if explicit_project else "using default project"
        _emit_notice(f"{label} ({scope}): {slug}", json_mode=json_mode, out=out)
    print(EXPORT_LINE_TEMPLATE.format(sid=sid), file=out)
    print(f"project: {slug}", file=out)
    print(f"timeline: {resolved_timeline_slug or NONE_PLACEHOLDER}", file=out)
    print(f"run: {on_disk_run_id or NONE_PLACEHOLDER}", file=out)
    print(f"role: {role}", file=out)
    if takeover_hint is not None:
        print(takeover_hint, file=out)
    return 0
