"""Command-line interface for Astrid timelines (Sprint 2 / extended Sprint 5b)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from astrid.core.project.current_run import read_current_run
from astrid.core.project.jsonio import read_json
from astrid.core.project.paths import project_dir
from astrid.core.session.binding import (
    SessionBindingError,
    resolve_current_session,
)
from astrid.core.task.events import read_events
from astrid.core.task.run_audit import _cost_by_source, _run_status

from . import clip_edits, crud
from .events.schema import ClipPosition, TimelineActor
from .integrity import verify
from .paths import assembly_identity_path, find_timeline_by_slug

_SESSION_GATE_HINT = (
    "A timeline command requires a bound session. "
    "Run 'astrid attach <project>' first."
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (crud.TimelineCrudError, clip_edits.ClipEditError, SessionBindingError) as exc:
        print(f"timelines: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"timelines: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid timelines",
        description="Create, inspect, and manage project timelines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- ls ---
    ls_parser = subparsers.add_parser("ls", help="List timelines in the current project.")
    ls_parser.add_argument(
        "--project",
        help="Project slug (required when no session is bound).",
    )
    ls_parser.set_defaults(handler=cmd_ls)

    # --- create ---
    create_parser = subparsers.add_parser("create", help="Create a timeline.")
    create_parser.add_argument("slug", help="Timeline slug (lowercase, letters/digits/hyphens).")
    create_parser.add_argument("--name", help="Human-readable name (defaults to slug).")
    create_parser.add_argument(
        "--default",
        action="store_true",
        dest="is_default",
        help="Set as the project default timeline.",
    )
    create_parser.set_defaults(handler=cmd_create)

    # --- show ---
    show_parser = subparsers.add_parser("show", help="Show a timeline.")
    show_parser.add_argument("slug", help="Timeline slug.")
    show_parser.add_argument(
        "--verify",
        action="store_true",
        help="Recompute integrity (sha256) for each final output.",
    )
    show_parser.add_argument(
        "--json",
        dest="json_out",
        action="store_true",
        help="Emit structured JSON instead of pretty-print.",
    )
    show_parser.set_defaults(handler=cmd_show)

    # --- rename ---
    rename_parser = subparsers.add_parser("rename", help="Rename a timeline slug.")
    rename_parser.add_argument("old_slug", metavar="slug", help="Current timeline slug.")
    rename_parser.add_argument("new_slug", metavar="new-slug", help="New timeline slug.")
    rename_parser.set_defaults(handler=cmd_rename)

    # --- finalize ---
    finalize_parser = subparsers.add_parser(
        "finalize", help="Record a final output with sha256 integrity."
    )
    finalize_parser.add_argument("slug", help="Timeline slug.")
    finalize_parser.add_argument("--output", required=True, help="Path to the output file.")
    finalize_parser.add_argument("--kind", default="unknown", help="Free-text output kind (mp4, transcript, etc.).")
    finalize_parser.add_argument(
        "--from-run",
        help="Run ID this output originates from (defaults to the current run).",
    )
    finalize_parser.add_argument(
        "--recorded-by", default="agent:cli", help="Agent identifier."
    )
    finalize_parser.set_defaults(handler=cmd_finalize)

    # --- tombstone ---
    tombstone_parser = subparsers.add_parser(
        "tombstone", help="Soft-delete a timeline (marks tombstoned, leaves files)."
    )
    tombstone_parser.add_argument("slug", help="Timeline slug.")
    tombstone_parser.set_defaults(handler=cmd_tombstone)

    # --- purge ---
    purge_parser = subparsers.add_parser(
        "purge", help="Hard-delete a timeline directory tree."
    )
    purge_parser.add_argument("slug", help="Timeline slug.")
    purge_parser.add_argument(
        "--yes-really",
        action="store_true",
        help="Confirm you really want to delete this timeline permanently.",
    )
    purge_parser.set_defaults(handler=cmd_purge)

    # --- set-default ---
    set_default_parser = subparsers.add_parser(
        "set-default", help="Set a timeline as the project default."
    )
    set_default_parser.add_argument("slug", help="Timeline slug.")
    set_default_parser.set_defaults(handler=cmd_set_default)

    # --- export (Sprint 5b) ---
    export_parser = subparsers.add_parser("export", help="Export a timeline bundle.")
    export_parser.add_argument("slug", help="Timeline slug.")
    export_parser.add_argument("--out", required=True, help="Output tarball path (.tar.gz).")
    export_parser.add_argument(
        "--include-aborted",
        action="store_true",
        help="Include aborted runs in the export bundle.",
    )
    export_parser.set_defaults(handler=cmd_export)

    # --- cost (Sprint 5b) ---
    cost_parser = subparsers.add_parser("cost", help="Show cost rollup for a timeline.")
    cost_parser.add_argument("slug", help="Timeline slug.")
    cost_parser.add_argument(
        "--json",
        dest="json_out",
        action="store_true",
        help="Emit structured JSON instead of pretty-print.",
    )
    cost_parser.add_argument(
        "--include-aborted",
        action="store_true",
        help="Include aborted runs in the cost rollup.",
    )
    cost_parser.set_defaults(handler=cmd_cost)

    # --- clip ---
    clip_parser = subparsers.add_parser("clip", help="Edit clips in a timeline.")
    clip_subs = clip_parser.add_subparsers(dest="clip_command", required=True)

    # clip add
    clip_add = clip_subs.add_parser("add", help="Add a clip to a timeline.")
    clip_add.add_argument("slug", help="Timeline slug.")
    clip_add.add_argument("--kind", required=True, choices=["visual", "audio", "text"], help="Clip kind.")
    clip_add.add_argument("--asset", required=True, help="Asset identifier.")
    pos_group = clip_add.add_mutually_exclusive_group()
    pos_group.add_argument("--at", type=int, dest="at_index", help="Insert at 0-based index.")
    pos_group.add_argument("--after", dest="after_id", help="Insert after clip id.")
    pos_group.add_argument("--before", dest="before_id", help="Insert before clip id.")
    clip_add.set_defaults(handler=cmd_clip_add)

    # clip remove
    clip_remove = clip_subs.add_parser("remove", help="Remove a clip from a timeline.")
    clip_remove.add_argument("slug", help="Timeline slug.")
    clip_remove.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_remove.set_defaults(handler=cmd_clip_remove)

    # clip move
    clip_move = clip_subs.add_parser("move", help="Move a clip to a new position.")
    clip_move.add_argument("slug", help="Timeline slug.")
    clip_move.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_move.add_argument("--to", required=True, dest="to_position", help="Target position: index, after:<id>, or before:<id>.")
    clip_move.set_defaults(handler=cmd_clip_move)

    # clip retime
    clip_retime = clip_subs.add_parser("retime", help="Change a clip's start time and duration.")
    clip_retime.add_argument("slug", help="Timeline slug.")
    clip_retime.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_retime.add_argument("--start", required=True, type=float, help="Start time in seconds (>= 0).")
    clip_retime.add_argument("--duration", required=True, type=float, help="Duration in seconds (> 0).")
    clip_retime.set_defaults(handler=cmd_clip_retime)

    # clip swap
    clip_swap = clip_subs.add_parser("swap", help="Swap the positions of two clips.")
    clip_swap.add_argument("slug", help="Timeline slug.")
    clip_swap.add_argument("--a", required=True, dest="clip_a", help="First clip identifier.")
    clip_swap.add_argument("--b", required=True, dest="clip_b", help="Second clip identifier.")
    clip_swap.set_defaults(handler=cmd_clip_swap)

    # clip replace
    clip_replace = clip_subs.add_parser("replace", help="Replace a clip with a different asset.")
    clip_replace.add_argument("slug", help="Timeline slug.")
    clip_replace.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_replace.add_argument("--with", required=True, dest="with_asset_id", metavar="ASSET_ID", help="Replacement asset identifier.")
    clip_replace.set_defaults(handler=cmd_clip_replace)

    # clip set-text
    clip_set_text = clip_subs.add_parser("set-text", help="Set the text content of a text clip.")
    clip_set_text.add_argument("slug", help="Timeline slug.")
    clip_set_text.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_set_text.add_argument("--text", required=True, help="Text content.")
    clip_set_text.set_defaults(handler=cmd_clip_set_text)

    # clip annotate
    clip_annotate = clip_subs.add_parser("annotate", help="Add a note annotation to a clip.")
    clip_annotate.add_argument("slug", help="Timeline slug.")
    clip_annotate.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_annotate.add_argument("--note", required=True, help="Annotation note text.")
    clip_annotate.set_defaults(handler=cmd_clip_annotate)

    return parser


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
        print(
            "timelines: no project specified; use --project <slug> or bind a session with 'astrid attach'",
            file=sys.stderr,
        )
        return 2

    rows = crud.list_timelines(project_slug)
    if not rows:
        print(f"(no timelines in project '{project_slug}')")
        return 0

    # Table header.
    print(f"{'SLUG':<20} {'NAME':<24} {'DEFAULT':<8} {'RUNS':>5} {'LAST FINALIZED':<20}")
    print("-" * 80)
    for row in rows:
        default_marker = "*" if row.is_default else ""
        last = row.last_finalized or "-"
        print(
            f"{row.slug:<20} {row.name:<24} {default_marker:<8} {row.run_count:>5} {last:<20}"
        )

    return 0


# ---------------------------------------------------------------------------
# Handler: create
# ---------------------------------------------------------------------------


def cmd_create(args: argparse.Namespace) -> int:
    session = _require_session()
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
    session = _require_session()
    data = crud.show_timeline(session.project, args.slug)
    if data is None:
        print(f"timeline '{args.slug}' not found", file=sys.stderr)
        return 1

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
            "assembly": dict(assembly.assembly),
            "final_outputs": outputs,
        }
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
    if assembly.assembly:
        import json as _json

        print(f"  keys: {sorted(assembly.assembly.keys())}")
    else:
        print("  (empty)")
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
    session = _require_session()
    result = crud.rename_timeline(
        session.project,
        args.old_slug,
        args.new_slug,
        actor=_timeline_actor_from_session(session),
    )
    print(f"renamed timeline '{args.old_slug}' -> '{result['slug']}'")
    return 0


# ---------------------------------------------------------------------------
# Handler: finalize
# ---------------------------------------------------------------------------


def cmd_finalize(args: argparse.Namespace) -> int:
    session = _require_session()
    from_run = args.from_run
    if from_run is None:
        from_run = read_current_run(session.project) or ""
        if not from_run:
            print(
                "timelines: no current run bound; pass --from-run explicitly",
                file=sys.stderr,
            )
            return 2

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
    session = _require_session()
    result = crud.tombstone_timeline(session.project, args.slug)
    print(
        f"tombstoned timeline '{result['slug']}' at {result['tombstoned_at']}"
    )
    return 0


# ---------------------------------------------------------------------------
# Handler: purge
# ---------------------------------------------------------------------------


def cmd_purge(args: argparse.Namespace) -> int:
    session = _require_session()

    if not args.yes_really:
        print(
            f"timelines: purge requires --yes-really to permanently delete timeline '{args.slug}'",
            file=sys.stderr,
        )
        return 2

    # Double-confirmation for interactive terminals.
    if sys.stdin.isatty():
        try:
            answer = input(
                f"Permanently delete timeline '{args.slug}'? This cannot be undone. [y/N] "
            )
        except (EOFError, KeyboardInterrupt):
            print("", file=sys.stderr)
            print("timelines: purge cancelled", file=sys.stderr)
            return 2
        if answer.strip().lower() not in ("y", "yes"):
            print("timelines: purge cancelled", file=sys.stderr)
            return 2

    crud.purge_timeline(session.project, args.slug)
    print(f"purged timeline '{args.slug}'")
    return 0


# ---------------------------------------------------------------------------
# Handler: set-default
# ---------------------------------------------------------------------------


def cmd_set_default(args: argparse.Namespace) -> int:
    session = _require_session()
    result = crud.set_default(session.project, args.slug)
    print(
        f"timeline '{result['slug']}' is now the default for project '{session.project}'"
    )
    return 0


# ---------------------------------------------------------------------------
# Handler: export (Sprint 5b)
# ---------------------------------------------------------------------------


def cmd_export(args: argparse.Namespace) -> int:
    """Export a timeline as a self-contained tarball bundle."""
    session = _require_session()
    data = crud.show_timeline(session.project, args.slug)
    if data is None:
        print(f"timeline '{args.slug}' not found", file=sys.stderr)
        return 1

    ulid = data["ulid"]
    manifest = data["manifest"]
    proj_root = project_dir(session.project)
    timelines_dir = proj_root / "timelines" / ulid
    runs_dir = proj_root / "runs"

    include_aborted = bool(getattr(args, "include_aborted", False))
    out_path = Path(args.out).expanduser().resolve()

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        manifest_entries: list[tuple[str, str]] = []

        def _add_file(src: Path, rel: str) -> None:
            dst = tmpdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            sha = hashlib.sha256(dst.read_bytes()).hexdigest()
            manifest_entries.append((rel, sha))

        # Copy timeline container files
        for name in ("assembly.json", "manifest.json", "display.json"):
            src = timelines_dir / name
            if src.is_file():
                _add_file(src, name)

        # Copy contributing runs
        for run_id in manifest.contributing_runs:
            run_root = runs_dir / run_id
            if not run_root.is_dir():
                continue

            # Filter aborted runs
            events_path = run_root / "events.jsonl"
            if events_path.exists():
                events = read_events(events_path)
                status = _run_status(events)
                if status == "aborted" and not include_aborted:
                    continue

            # Copy plan.json (from project root)
            plan_path = proj_root / "plan.json"
            if plan_path.is_file():
                _add_file(plan_path, f"runs/{run_id}/plan.json")

            # Copy events.jsonl
            if events_path.is_file():
                _add_file(events_path, f"runs/{run_id}/events.jsonl")

            # Copy produces/ tree
            produces_root = run_root / "produces"
            if produces_root.is_dir():
                for src_file in produces_root.rglob("*"):
                    if src_file.is_file():
                        rel = str(Path("runs") / run_id / "produces" / src_file.relative_to(produces_root))
                        _add_file(src_file, rel)

            # Copy run.json if present
            run_json = run_root / "run.json"
            if run_json.is_file():
                _add_file(run_json, f"runs/{run_id}/run.json")

        # Write MANIFEST.txt
        manifest_txt = tmpdir / "MANIFEST.txt"
        lines = [f"{sha}  {rel}" for rel, sha in sorted(manifest_entries)]
        manifest_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Build tarball
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out_path, "w:gz") as tar:
            for member in sorted(tmpdir.iterdir()):
                tar.add(member, arcname=member.name)

    print(f"exported timeline '{args.slug}' to {out_path}")
    return 0


# ---------------------------------------------------------------------------
# Handler: cost (Sprint 5b)
# ---------------------------------------------------------------------------


def cmd_cost(args: argparse.Namespace) -> int:
    """Aggregate cost across all contributing runs in a timeline."""
    session = _require_session()
    data = crud.show_timeline(session.project, args.slug)
    if data is None:
        print(f"timeline '{args.slug}' not found", file=sys.stderr)
        return 1

    manifest = data["manifest"]
    proj_root = project_dir(session.project)
    runs_dir = proj_root / "runs"
    include_aborted = bool(getattr(args, "include_aborted", False))

    # Aggregate costs across all contributing runs
    by_source: dict[str, float] = {}
    grand_total = 0.0
    run_count = 0

    for run_id in manifest.contributing_runs:
        run_root = runs_dir / run_id
        if not run_root.is_dir():
            continue
        events_path = run_root / "events.jsonl"
        if not events_path.exists():
            continue
        events = read_events(events_path)

        # Filter aborted runs
        status = _run_status(events)
        if status == "aborted" and not include_aborted:
            continue

        run_count += 1
        cost_summary = _cost_by_source(events)
        for source, info in cost_summary.items():
            if isinstance(info, dict):
                amt = info.get("amount", 0)
                by_source[source] = by_source.get(source, 0.0) + float(amt)
                grand_total += float(amt)

    json_out = bool(getattr(args, "json_out", False))
    if json_out:
        payload: dict[str, Any] = {
            "slug": args.slug,
            "project": session.project,
            "contributing_runs": run_count,
            "total_runs_in_manifest": len(manifest.contributing_runs),
            "include_aborted": include_aborted,
            "grand_total": round(grand_total, 6),
            "by_source": {
                source: round(amt, 6) for source, amt in sorted(by_source.items())
            },
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Cost rollup for timeline '{args.slug}' ({run_count} contributing runs):")
    print()
    if not by_source:
        print("  (no cost data)")
    else:
        for source in sorted(by_source):
            amt = by_source[source]
            print(f"  {source:<20} ${amt:>10.4f}")
    print(f"  {'─' * 32}")
    print(f"  {'TOTAL':<20} ${grand_total:>10.4f}")
    return 0


# ---------------------------------------------------------------------------
# Handler: clip (8 verbs)
# ---------------------------------------------------------------------------


def _parse_clip_position(args: argparse.Namespace) -> ClipPosition | None:
    """Normalise CLI position flags into a :class:`ClipPosition`."""
    at_index = getattr(args, "at_index", None)
    after_id = getattr(args, "after_id", None)
    before_id = getattr(args, "before_id", None)

    if at_index is not None:
        return ClipPosition(mode="index", index=at_index)
    if after_id is not None:
        return ClipPosition(mode="after", ref_clip_id=after_id)
    if before_id is not None:
        return ClipPosition(mode="before", ref_clip_id=before_id)
    return None


def _parse_move_position(raw: str) -> ClipPosition:
    """Parse ``--to`` syntax: bare integer → index, ``after:<id>``, ``before:<id>``."""
    raw = raw.strip()
    if raw.startswith("after:"):
        ref = raw[len("after:"):]
        if not ref:
            raise clip_edits.ClipEditError("--to after:<id> requires a non-empty clip id")
        return ClipPosition(mode="after", ref_clip_id=ref)
    if raw.startswith("before:"):
        ref = raw[len("before:"):]
        if not ref:
            raise clip_edits.ClipEditError("--to before:<id> requires a non-empty clip id")
        return ClipPosition(mode="before", ref_clip_id=ref)
    try:
        idx = int(raw)
    except ValueError:
        raise clip_edits.ClipEditError(
            f"--to must be an index, after:<id>, or before:<id>; got {raw!r}"
        )
    return ClipPosition(mode="index", index=idx)


def _resolve_clip_backend_name(project_slug: str, slug: str) -> str:
    """Read the identity sidecar to determine the backend name for a timeline.

    Returns ``\"local_fs\"`` when no explicit backend preference is set,
    or ``\"supabase\"`` when the sidecar requests it.
    """
    found = find_timeline_by_slug(project_slug, slug)
    if found is None:
        raise clip_edits.ClipEditError(
            f"timeline '{slug}' not found in project '{project_slug}'"
        )
    ulid, _ = found
    identity = read_json(assembly_identity_path(project_slug, ulid))
    if not isinstance(identity, dict):
        raise clip_edits.ClipEditError("timeline identity sidecar is malformed")
    preferred = identity.get("backend")
    if isinstance(preferred, str) and preferred.strip().lower() == "supabase":
        return "supabase"
    return "local_fs"


def _clip_success(event: "TimelineEvent", backend_name: str) -> str:
    """Format a one-line success message for clip commands."""
    return (
        f"clip: event {event.event_id}, kind={event.kind}, "
        f"timeline={event.timeline_id}, backend={backend_name}"
    )


def cmd_clip_add(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    pos = _parse_clip_position(args)
    event = clip_edits.add_clip(
        session.project,
        args.slug,
        kind=args.kind,
        asset_id=args.asset,
        position=pos,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_remove(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    event = clip_edits.remove_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_move(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    pos = _parse_move_position(args.to_position)
    event = clip_edits.move_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        position=pos,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_retime(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    event = clip_edits.retime_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        start=args.start,
        duration=args.duration,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_swap(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    event = clip_edits.swap_clips(
        session.project,
        args.slug,
        clip_a_id=args.clip_a,
        clip_b_id=args.clip_b,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_replace(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    event = clip_edits.replace_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        with_asset_id=args.with_asset_id,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_set_text(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    event = clip_edits.set_clip_text(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        text=args.text,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_annotate(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    event = clip_edits.annotate_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        note=args.note,
        actor=_timeline_actor_from_session(session),
    )
    print(_clip_success(event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_session(slug: str | None = None) -> Any:
    # T9 / FLAG-S1-003: optional slug for file-bound fallback; env-only when
    # caller has no --project context to plumb.
    session = resolve_current_session(slug=slug)
    if session is None:
        raise SessionBindingError(_SESSION_GATE_HINT)
    return session


def _timeline_actor_from_session(session: Any) -> TimelineActor:
    agent_id = getattr(session, "agent_id", "") or "unknown-agent"
    session_id = getattr(session, "id", "") or "unknown-session"
    return TimelineActor(
        type="agent",
        id=f"{agent_id}:{session_id}",
        display=agent_id,
    )
