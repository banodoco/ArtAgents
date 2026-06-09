"""Timeline CRUD command handlers.

Extracted from ``astrid/core/timeline/cli.py`` during M4 giant-file split.
These handlers implement the core timeline lifecycle commands (ls, create,
show, rename, finalize, tombstone, purge, set-default).
"""

from __future__ import annotations

import argparse
import sys

from astrid.core.contracts.errors import AstridError
from astrid.core.project.current_run import read_current_run
from astrid.core.session.binding import resolve_current_session

from . import crud
from ._shared import _expected_version_kwargs, _timeline_actor_from_session
from .integrity import verify


# ---------------------------------------------------------------------------
# Handler: ls
# ---------------------------------------------------------------------------


def cmd_ls(args: argparse.Namespace) -> int:
    # T9 / FLAG-S1-003: plumb slug only when --project provided; else env-only.
    session = resolve_current_session(slug=getattr(args, "project", None) or None)
    project_slug = args.project

    if session is not None:
        project_slug = project_slug or session.project
    if not project_slug:
        raise AstridError(
            "timelines: no project specified; use --project <slug> or bind a session with 'astrid attach'",
            recovery_command="astrid attach <project>",
        )

    rows = crud.list_timelines(
        project_slug,
        include_tombstoned=bool(getattr(args, "include_tombstoned", False)),
    )
    if not rows:
        print(f"(no timelines in project '{project_slug}')")
        return 0

    # Table header.
    print(f"{'SLUG':<20} {'NAME':<24} {'DEFAULT':<8} {'RUNS':>5} {'TOMBSTONED':<20} {'LAST FINALIZED':<20}")
    print("-" * 102)
    for row in rows:
        default_marker = "*" if row.is_default else ""
        last = row.last_finalized or "-"
        tombstoned = row.tombstoned_at or "-"
        print(
            f"{row.slug:<20} {row.name:<24} {default_marker:<8} {row.run_count:>5} {tombstoned:<20} {last:<20}"
        )

    return 0


# ---------------------------------------------------------------------------
# Handler: create
# ---------------------------------------------------------------------------


def cmd_create(args: argparse.Namespace) -> int:
    from .cli import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    result = crud.create_timeline(
        session.project,
        args.slug,
        name=args.name,
        is_default=args.is_default,
    )
    print(f"created timeline '{result['slug']}' (ulid: {result['ulid']})")
    if args.is_default:
        print(f"set as default timeline for project '{session.project}'")
    return 0


# ---------------------------------------------------------------------------
# Handler: show
# ---------------------------------------------------------------------------


def cmd_show(args: argparse.Namespace) -> int:
    from .cli import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    data = crud.show_timeline(
        session.project,
        args.slug,
        verify=bool(getattr(args, "verify", False)),
    )
    if data is None:
        raise AstridError(
            f"timeline '{args.slug}' not found",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        )

    display = data["display"]
    manifest = data["manifest"]
    assembly = data["assembly"]
    ulid = data["ulid"]

    if getattr(args, "json_out", False):
        import json as _json

        outputs = []
        for fo in manifest.final_outputs:
            if getattr(args, "verify", False):
                status = verify(fo)
            else:
                status = fo.check_status
            outputs.append({
                "kind": fo.kind,
                "path": fo.path,
                "sha256": fo.sha256,
                "size": fo.size,
                "check_status": status,
                "from_run": fo.from_run,
                "recorded_at": fo.recorded_at,
                "recorded_by": fo.recorded_by,
            })
        payload = {
            "ulid": ulid,
            "slug": display.slug,
            "name": display.name,
            "is_default": display.is_default,
            "tombstoned_at": manifest.tombstoned_at,
            "contributing_runs": manifest.contributing_runs,
            "assembly": dict(assembly),
            "final_outputs": outputs,
        }
        if "verification" in data:
            payload["verification"] = data["verification"]
        print(_json.dumps(payload, indent=2, default=str))
        return 0

    print(f"Timeline: {display.name}")
    print(f"  slug:      {display.slug}")
    print(f"  ulid:      {ulid}")
    print(f"  default:   {display.is_default}")
    if manifest.tombstoned_at:
        print(f"  tombstoned: {manifest.tombstoned_at}")
    print(f"  contributing runs: {len(manifest.contributing_runs)}")
    print()

    print("Assembly:")
    if assembly:
        import json as _json

        print(f"  keys: {sorted(assembly.keys())}")
    else:
        print("  (empty)")
    print()
    if "verification" in data:
        verification = data["verification"]
        status = "ok" if verification.get("ok") else "failed"
        print(f"Verification: {status}")
        print(f"  event log: {verification.get('event_log')}")
        print(f"  checked events: {verification.get('checked_events')}")
        if verification.get("error"):
            print(f"  error: {verification.get('error')}")
        print()

    print(f"Final outputs ({len(manifest.final_outputs)}):")
    if not manifest.final_outputs:
        print("  (none)")
    else:
        for fo in manifest.final_outputs:
            if args.verify:
                status = verify(fo)
            else:
                status = fo.check_status
            marker = ""
            if status != "ok":
                marker = f"  [{status.upper()}]"
            print(f"  - {fo.kind:<16} {fo.path}")
            print(f"    sha256: {fo.sha256}")
            print(f"    size:   {fo.size} bytes")
            print(f"    status: {status}{marker}")
            print(f"    run:    {fo.from_run}")
            print(f"    at:     {fo.recorded_at}")
            print()

    return 0


# ---------------------------------------------------------------------------
# Handler: rename
# ---------------------------------------------------------------------------


def cmd_rename(args: argparse.Namespace) -> int:
    from .cli import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    extra = _expected_version_kwargs(args)
    result = crud.rename_timeline(
        session.project,
        args.old_slug,
        args.new_slug,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(f"renamed timeline '{args.old_slug}' -> '{result['slug']}'")
    return 0


# ---------------------------------------------------------------------------
# Handler: finalize
# ---------------------------------------------------------------------------


def cmd_finalize(args: argparse.Namespace) -> int:
    from .cli import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    from_run = args.from_run
    if from_run is None:
        from_run = read_current_run(session.project) or ""
        if not from_run:
            raise AstridError(
                "timelines: no current run bound; pass --from-run explicitly",
                recovery_command=f"astrid timelines finalize {args.slug} <output> --from-run <run-id>",
                state_snapshot={"timeline": args.slug},
            )

    fo = crud.finalize_output(
        session.project,
        args.slug,
        args.output,
        kind=args.kind,
        from_run=from_run,
        recorded_by=args.recorded_by,
    )
    print(
        f"finalized '{fo.kind}' output for timeline '{args.slug}' "
        f"(sha256: {fo.sha256[:16]}..., size: {fo.size} bytes)"
    )
    return 0


# ---------------------------------------------------------------------------
# Handler: tombstone
# ---------------------------------------------------------------------------


def cmd_tombstone(args: argparse.Namespace) -> int:
    from .cli import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    result = crud.tombstone_timeline(session.project, args.slug)
    print(
        f"tombstoned timeline '{result['slug']}' at {result['tombstoned_at']}"
    )
    return 0


# ---------------------------------------------------------------------------
# Handler: purge
# ---------------------------------------------------------------------------


def cmd_purge(args: argparse.Namespace) -> int:
    from .cli import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))

    if not args.yes_really:
        raise AstridError(
            f"timelines: purge requires --yes-really to permanently delete timeline '{args.slug}'",
            recovery_command=f"astrid timelines purge {args.slug} --yes-really",
            state_snapshot={"timeline": args.slug},
        )

    # Double-confirmation for interactive terminals.
    if sys.stdin.isatty():
        try:
            answer = input(
                f"Permanently delete timeline '{args.slug}'? This cannot be undone. [y/N] "
            )
        except (EOFError, KeyboardInterrupt):
            raise AstridError(
                "timelines: purge cancelled",
                recovery_command=f"astrid timelines purge {args.slug} --yes-really",
            )
        if answer.strip().lower() not in ("y", "yes"):
            raise AstridError(
                "timelines: purge cancelled",
                recovery_command=f"astrid timelines purge {args.slug} --yes-really",
            )

    crud.purge_timeline(session.project, args.slug)
    print(f"purged timeline '{args.slug}'")
    return 0


# ---------------------------------------------------------------------------
# Handler: set-default
# ---------------------------------------------------------------------------


def cmd_set_default(args: argparse.Namespace) -> int:
    from .cli import _require_session  # noqa: PLC0415

    session = _require_session(slug=getattr(args, "project", None))
    result = crud.set_default(session.project, args.slug)
    print(
        f"timeline '{result['slug']}' is now the default for project '{session.project}'"
    )
    return 0
