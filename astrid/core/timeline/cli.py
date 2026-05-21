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

from . import (
    arrangement_edits,
    audio_edits,
    clip_edits,
    crud,
    effect_edits,
    pool_edits,
    theme_edits,
    track_edits,
    transition_edits,
)
from ._edit_helpers import TimelineEditError
from .eventlog import EventLogError
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
    except (crud.TimelineCrudError, TimelineEditError, SessionBindingError, EventLogError) as exc:
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
    _add_expected_version_arg(rename_parser)
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

    # --- history (m7) ---
    history_parser = subparsers.add_parser(
        "history", help="Read the event history of a timeline."
    )
    history_parser.add_argument(
        "slug_or_id", help="Timeline slug, ULID, or event-stream UUID."
    )
    history_parser.add_argument(
        "--since",
        dest="since_event_id",
        default=None,
        help="Start reading after this event ID.",
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of events to return (default: 50).",
    )
    history_parser.set_defaults(handler=cmd_history)

    # --- diff (m7) ---
    diff_parser = subparsers.add_parser(
        "diff", help="Semantic diff between two events."
    )
    diff_parser.add_argument(
        "slug_or_id", help="Timeline slug, ULID, or event-stream UUID."
    )
    diff_parser.add_argument(
        "--from",
        required=True,
        dest="from_event_id",
        help="Starting event ID for the diff.",
    )
    diff_parser.add_argument(
        "--to",
        required=True,
        dest="to_event_id",
        help="Ending event ID for the diff.",
    )
    diff_parser.add_argument(
        "--with-state",
        action="store_true",
        help="Include projected before/after assembly snapshots.",
    )
    diff_parser.set_defaults(handler=cmd_diff)

    # --- audit (m7) ---
    audit_parser = subparsers.add_parser(
        "audit", help="Verify event chain integrity and projection parity."
    )
    audit_parser.add_argument(
        "slug_or_id", help="Timeline slug, ULID, or event-stream UUID."
    )
    audit_parser.add_argument(
        "--include-ops",
        action="store_true",
        dest="include_ops",
        help="Include operational failure logs in the audit report.",
    )
    audit_parser.set_defaults(handler=cmd_audit)

    # --- preview (m7) ---
    preview_parser = subparsers.add_parser(
        "preview", help="Project a past state at a specific event."
    )
    preview_parser.add_argument(
        "slug_or_id", help="Timeline slug, ULID, or event-stream UUID."
    )
    preview_parser.add_argument(
        "--at",
        required=True,
        dest="at_event_id",
        help="Event ID to project state at.",
    )
    preview_parser.add_argument(
        "--out",
        dest="out_path",
        default=None,
        help="Write projected state to this file (default: stdout).",
    )
    preview_parser.set_defaults(handler=cmd_preview)

    # --- who-edited (m7) ---
    who_edited_parser = subparsers.add_parser(
        "who-edited", help="Show actor rollup for a timeline."
    )
    who_edited_parser.add_argument(
        "slug_or_id", help="Timeline slug, ULID, or event-stream UUID."
    )
    who_edited_parser.set_defaults(handler=cmd_who_edited)

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
    _add_expected_version_arg(clip_add)
    clip_add.set_defaults(handler=cmd_clip_add)

    # clip remove
    clip_remove = clip_subs.add_parser("remove", help="Remove a clip from a timeline.")
    clip_remove.add_argument("slug", help="Timeline slug.")
    clip_remove.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    _add_expected_version_arg(clip_remove)
    clip_remove.set_defaults(handler=cmd_clip_remove)

    # clip move
    clip_move = clip_subs.add_parser("move", help="Move a clip to a new position.")
    clip_move.add_argument("slug", help="Timeline slug.")
    clip_move.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_move.add_argument("--to", required=True, dest="to_position", help="Target position: index, after:<id>, or before:<id>.")
    _add_expected_version_arg(clip_move)
    clip_move.set_defaults(handler=cmd_clip_move)

    # clip retime
    clip_retime = clip_subs.add_parser("retime", help="Change a clip's start time and duration.")
    clip_retime.add_argument("slug", help="Timeline slug.")
    clip_retime.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_retime.add_argument("--start", required=True, type=float, help="Start time in seconds (>= 0).")
    clip_retime.add_argument("--duration", required=True, type=float, help="Duration in seconds (> 0).")
    _add_expected_version_arg(clip_retime)
    clip_retime.set_defaults(handler=cmd_clip_retime)

    # clip swap
    clip_swap = clip_subs.add_parser("swap", help="Swap the positions of two clips.")
    clip_swap.add_argument("slug", help="Timeline slug.")
    clip_swap.add_argument("--a", required=True, dest="clip_a", help="First clip identifier.")
    clip_swap.add_argument("--b", required=True, dest="clip_b", help="Second clip identifier.")
    _add_expected_version_arg(clip_swap)
    clip_swap.set_defaults(handler=cmd_clip_swap)

    # clip replace
    clip_replace = clip_subs.add_parser("replace", help="Replace a clip with a different asset.")
    clip_replace.add_argument("slug", help="Timeline slug.")
    clip_replace.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_replace.add_argument("--with", required=True, dest="with_asset_id", metavar="ASSET_ID", help="Replacement asset identifier.")
    _add_expected_version_arg(clip_replace)
    clip_replace.set_defaults(handler=cmd_clip_replace)

    # clip set-text
    clip_set_text = clip_subs.add_parser("set-text", help="Set the text content of a text clip.")
    clip_set_text.add_argument("slug", help="Timeline slug.")
    clip_set_text.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_set_text.add_argument("--text", required=True, help="Text content.")
    _add_expected_version_arg(clip_set_text)
    clip_set_text.set_defaults(handler=cmd_clip_set_text)

    # clip annotate
    clip_annotate = clip_subs.add_parser("annotate", help="Add a note annotation to a clip.")
    clip_annotate.add_argument("slug", help="Timeline slug.")
    clip_annotate.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_annotate.add_argument("--note", required=True, help="Annotation note text.")
    _add_expected_version_arg(clip_annotate)
    clip_annotate.set_defaults(handler=cmd_clip_annotate)

    # --- transition ---
    trans_parser = subparsers.add_parser("transition", help="Manage transitions between clips.")
    trans_subs = trans_parser.add_subparsers(dest="transition_command", required=True)

    # transition set
    trans_set = trans_subs.add_parser("set", help="Set a transition between two clips.")
    trans_set.add_argument("slug", help="Timeline slug.")
    trans_set.add_argument("--between", required=True, metavar="LEFT,RIGHT",
                           help="Two clip ids separated by comma (left clip, right clip).")
    trans_set.add_argument("--kind", default="cross-fade", help="Transition kind (default: cross-fade).")
    trans_set.add_argument("--duration", type=float, default=0.5, dest="duration_seconds",
                           help="Transition duration in seconds (default: 0.5).")
    _add_expected_version_arg(trans_set)
    trans_set.set_defaults(handler=cmd_transition_set)

    # transition remove
    trans_remove = trans_subs.add_parser("remove", help="Remove a transition between two clips.")
    trans_remove.add_argument("slug", help="Timeline slug.")
    trans_remove.add_argument("--between", required=True, metavar="LEFT,RIGHT",
                              help="Two clip ids separated by comma (left clip, right clip).")
    _add_expected_version_arg(trans_remove)
    trans_remove.set_defaults(handler=cmd_transition_remove)

    # --- effect ---
    effect_parser = subparsers.add_parser("effect", help="Manage clip effects.")
    effect_subs = effect_parser.add_subparsers(dest="effect_command", required=True)

    # effect add
    effect_add_p = effect_subs.add_parser("add", help="Add an effect to a clip.")
    effect_add_p.add_argument("slug", help="Timeline slug.")
    effect_add_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    effect_add_p.add_argument("--effect-id", required=True, dest="effect_id", help="Effect identifier.")
    effect_add_p.add_argument("--params", action="append", dest="params_raw", metavar="k=v",
                              help="Effect parameter as k=v (repeatable).")
    _add_expected_version_arg(effect_add_p)
    effect_add_p.set_defaults(handler=cmd_effect_add)

    # effect remove
    effect_remove_p = effect_subs.add_parser("remove", help="Remove an effect from a clip.")
    effect_remove_p.add_argument("slug", help="Timeline slug.")
    effect_remove_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    effect_remove_p.add_argument("--effect-id", required=True, dest="effect_id", help="Effect identifier.")
    _add_expected_version_arg(effect_remove_p)
    effect_remove_p.set_defaults(handler=cmd_effect_remove)

    # effect tune
    effect_tune_p = effect_subs.add_parser("tune", help="Tune an effect parameter.")
    effect_tune_p.add_argument("slug", help="Timeline slug.")
    effect_tune_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    effect_tune_p.add_argument("--effect-id", required=True, dest="effect_id", help="Effect identifier.")
    effect_tune_p.add_argument("--param", required=True, help="Parameter name (k).")
    effect_tune_p.add_argument("--value", required=True, help="Parameter value (parsed as JSON).")
    _add_expected_version_arg(effect_tune_p)
    effect_tune_p.set_defaults(handler=cmd_effect_tune)

    # --- theme ---
    theme_parser = subparsers.add_parser("theme", help="Manage timeline theme.")
    theme_subs = theme_parser.add_subparsers(dest="theme_command", required=True)

    # theme set
    theme_set_p = theme_subs.add_parser("set", help="Set the active theme.")
    theme_set_p.add_argument("slug", help="Timeline slug.")
    theme_set_p.add_argument("--theme", required=True, dest="theme_id", help="Theme identifier.")
    _add_expected_version_arg(theme_set_p)
    theme_set_p.set_defaults(handler=cmd_theme_set)

    # theme override
    theme_override_p = theme_subs.add_parser("override", help="Override a theme namespace value.")
    theme_override_p.add_argument("slug", help="Timeline slug.")
    theme_override_p.add_argument("--override-id", required=True, dest="override_id",
                                  help="Override namespace (visual|generation|voice|audio|pacing).")
    theme_override_p.add_argument("--value", required=True, help="Override value (parsed as JSON).")
    _add_expected_version_arg(theme_override_p)
    theme_override_p.set_defaults(handler=cmd_theme_override)

    # --- track ---
    track_parser = subparsers.add_parser("track", help="Manage timeline tracks.")
    track_subs = track_parser.add_subparsers(dest="track_command", required=True)

    # track add
    track_add_p = track_subs.add_parser("add", help="Add a track.")
    track_add_p.add_argument("slug", help="Timeline slug.")
    track_add_p.add_argument("--kind", required=True, choices=["visual", "audio"],
                             help="Track kind: visual or audio.")
    track_add_p.add_argument("--label", default=None, help="Optional human-readable label.")
    track_add_p.add_argument("--track-id", default=None, dest="track_id",
                             help="Track identifier (auto-generated UUID if omitted).")
    _add_expected_version_arg(track_add_p)
    track_add_p.set_defaults(handler=cmd_track_add)

    # track remove
    track_remove_p = track_subs.add_parser("remove", help="Remove a track.")
    track_remove_p.add_argument("slug", help="Timeline slug.")
    track_remove_p.add_argument("--track-id", required=True, dest="track_id", help="Track identifier.")
    _add_expected_version_arg(track_remove_p)
    track_remove_p.set_defaults(handler=cmd_track_remove)

    # --- audio ---
    audio_parser = subparsers.add_parser("audio", help="Manage clip audio bindings.")
    audio_subs = audio_parser.add_subparsers(dest="audio_command", required=True)

    # audio bind
    audio_bind_p = audio_subs.add_parser("bind", help="Bind audio asset to a clip.")
    audio_bind_p.add_argument("slug", help="Timeline slug.")
    audio_bind_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    audio_bind_p.add_argument("--asset", required=True, dest="asset_id", help="Audio asset identifier.")
    _add_expected_version_arg(audio_bind_p)
    audio_bind_p.set_defaults(handler=cmd_audio_bind)

    # audio unbind
    audio_unbind_p = audio_subs.add_parser("unbind", help="Unbind audio from a clip.")
    audio_unbind_p.add_argument("slug", help="Timeline slug.")
    audio_unbind_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    _add_expected_version_arg(audio_unbind_p)
    audio_unbind_p.set_defaults(handler=cmd_audio_unbind)

    # --- pool ---
    pool_parser = subparsers.add_parser("pool", help="Manage asset pool.")
    pool_subs = pool_parser.add_subparsers(dest="pool_command", required=True)

    # pool add
    pool_add_p = pool_subs.add_parser("add", help="Add an asset to the pool.")
    pool_add_p.add_argument("slug", help="Timeline slug.")
    pool_add_p.add_argument("--asset", required=True, dest="asset_id", help="Asset identifier.")
    _add_expected_version_arg(pool_add_p)
    pool_add_p.set_defaults(handler=cmd_pool_add)

    # pool remove
    pool_remove_p = pool_subs.add_parser("remove", help="Remove an asset from the pool.")
    pool_remove_p.add_argument("slug", help="Timeline slug.")
    pool_remove_p.add_argument("--asset-id", required=True, dest="asset_id", help="Asset identifier.")
    _add_expected_version_arg(pool_remove_p)
    pool_remove_p.set_defaults(handler=cmd_pool_remove)

    # pool score
    pool_score_p = pool_subs.add_parser("score", help="Score a pool asset.")
    pool_score_p.add_argument("slug", help="Timeline slug.")
    pool_score_p.add_argument("--asset-id", required=True, dest="asset_id", help="Asset identifier.")
    pool_score_p.add_argument("--score", type=float, required=True, help="Score between 0 and 1.")
    _add_expected_version_arg(pool_score_p)
    pool_score_p.set_defaults(handler=cmd_pool_score)

    # --- arrangement ---
    arr_parser = subparsers.add_parser("arrangement", help="Manage arrangement.")
    arr_subs = arr_parser.add_subparsers(dest="arrangement_command", required=True)

    # arrangement set
    arr_set_p = arr_subs.add_parser("set", help="Replace the timeline arrangement from a JSON file.")
    arr_set_p.add_argument("slug", help="Timeline slug.")
    arr_set_p.add_argument("--from-json", required=True, dest="from_json",
                           help="Path to a JSON file containing the new arrangement.")
    _add_expected_version_arg(arr_set_p)
    arr_set_p.set_defaults(handler=cmd_arrangement_set)

    # arrangement show
    arr_show_p = arr_subs.add_parser("show", help="Show the current arrangement.")
    arr_show_p.add_argument("slug", help="Timeline slug.")
    arr_show_p.add_argument("--json", dest="json_out", action="store_true",
                            help="Emit structured JSON.")
    arr_show_p.set_defaults(handler=cmd_arrangement_show)

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

        # Repair assembly.json from the event log before export (ensures the
        # exported tarball carries the current projected state even when the
        # on-disk compatibility file is stale).
        from .paths import load_assembly_json_with_repair
        load_assembly_json_with_repair(timelines_dir)

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
    extra = _expected_version_kwargs(args)
    event = clip_edits.add_clip(
        session.project,
        args.slug,
        kind=args.kind,
        asset_id=args.asset,
        position=pos,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_remove(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.remove_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_move(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    pos = _parse_move_position(args.to_position)
    extra = _expected_version_kwargs(args)
    event = clip_edits.move_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        position=pos,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_retime(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.retime_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        start=args.start,
        duration=args.duration,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_swap(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.swap_clips(
        session.project,
        args.slug,
        clip_a_id=args.clip_a,
        clip_b_id=args.clip_b,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_replace(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.replace_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        with_asset_id=args.with_asset_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_set_text(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.set_clip_text(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        text=args.text,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


def cmd_clip_annotate(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.annotate_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        note=args.note,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_clip_success(event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: transition (2 verbs)
# ---------------------------------------------------------------------------


def _parse_between(raw: str) -> tuple[str, str]:
    """Parse ``--between LEFT,RIGHT`` into ``(left_clip_id, right_clip_id)``."""
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        raise TimelineEditError(
            f"--between must be LEFT,RIGHT (comma-separated), got {raw!r}"
        )
    left, right = parts
    if not left or not right:
        raise TimelineEditError("--between clip ids must be non-empty")
    return left, right


def cmd_transition_set(args: argparse.Namespace) -> int:
    session = _require_session()
    left, right = _parse_between(args.between)
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = transition_edits.transition_set(
        session.project,
        args.slug,
        left_clip_id=left,
        right_clip_id=right,
        kind=args.kind,
        duration_seconds=args.duration_seconds,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("transition", event, backend_name))
    return 0


def cmd_transition_remove(args: argparse.Namespace) -> int:
    session = _require_session()
    left, right = _parse_between(args.between)
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = transition_edits.transition_remove(
        session.project,
        args.slug,
        left_clip_id=left,
        right_clip_id=right,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("transition", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: effect (3 verbs)
# ---------------------------------------------------------------------------


def _parse_kv(raw: str) -> tuple[str, str]:
    """Parse ``k=v`` into ``(k, v)``."""
    parts = raw.split("=", 1)
    if len(parts) != 2:
        raise TimelineEditError(f"--params must be k=v, got {raw!r}")
    return parts[0].strip(), parts[1].strip()


def _parse_params(raw_list: list[str] | None) -> dict[str, Any] | None:
    """Convert repeated ``k=v`` args into a dict."""
    if not raw_list:
        return None
    result: dict[str, Any] = {}
    for item in raw_list:
        k, v = _parse_kv(item)
        result[k] = v
    return result


def _parse_json_value(raw: str, *, flag: str) -> Any:
    """Parse a CLI JSON value, surfacing a user-facing error on invalid JSON."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TimelineEditError(f"{flag} must be valid JSON: {exc.msg}") from exc


def _edit_success(domain: str, event: "TimelineEvent", backend_name: str) -> str:
    """Format a one-line success message for non-clip timeline edit commands."""
    return (
        f"{domain}: event {event.event_id}, kind={event.kind}, "
        f"timeline={event.timeline_id}, backend={backend_name}"
    )


def cmd_effect_add(args: argparse.Namespace) -> int:
    session = _require_session()
    params = _parse_params(args.params_raw)
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = effect_edits.effect_add(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        effect_id=args.effect_id,
        params=params,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("effect", event, backend_name))
    return 0


def cmd_effect_remove(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = effect_edits.effect_remove(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        effect_id=args.effect_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("effect", event, backend_name))
    return 0


def cmd_effect_tune(args: argparse.Namespace) -> int:
    session = _require_session()
    value = _parse_json_value(args.value, flag="--value")
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = effect_edits.effect_tune(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        effect_id=args.effect_id,
        param=args.param,
        value=value,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("effect", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: theme (2 verbs)
# ---------------------------------------------------------------------------


def cmd_theme_set(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = theme_edits.theme_set(
        session.project,
        args.slug,
        theme_id=args.theme_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("theme", event, backend_name))
    return 0


def cmd_theme_override(args: argparse.Namespace) -> int:
    session = _require_session()
    value = _parse_json_value(args.value, flag="--value")
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = theme_edits.theme_override(
        session.project,
        args.slug,
        override_id=args.override_id,
        value=value,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("theme", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: track (2 verbs)
# ---------------------------------------------------------------------------


def cmd_track_add(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    from uuid import uuid4 as _uuid4

    track_id = args.track_id or str(_uuid4())
    extra = _expected_version_kwargs(args)
    event = track_edits.track_add(
        session.project,
        args.slug,
        track_id=track_id,
        kind=args.kind,
        label=args.label,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("track", event, backend_name))
    return 0


def cmd_track_remove(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = track_edits.track_remove(
        session.project,
        args.slug,
        track_id=args.track_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("track", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: audio (2 verbs)
# ---------------------------------------------------------------------------


def cmd_audio_bind(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = audio_edits.audio_bind(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        asset_id=args.asset_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("audio", event, backend_name))
    return 0


def cmd_audio_unbind(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = audio_edits.audio_unbind(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("audio", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: pool (3 verbs)
# ---------------------------------------------------------------------------


def cmd_pool_add(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = pool_edits.pool_asset_add(
        session.project,
        args.slug,
        asset_id=args.asset_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("pool", event, backend_name))
    return 0


def cmd_pool_remove(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = pool_edits.pool_asset_remove(
        session.project,
        args.slug,
        asset_id=args.asset_id,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("pool", event, backend_name))
    return 0


def cmd_pool_score(args: argparse.Namespace) -> int:
    session = _require_session()
    if args.score < 0 or args.score > 1:
        raise TimelineEditError("score must be between 0 and 1")
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = pool_edits.pool_asset_score(
        session.project,
        args.slug,
        asset_id=args.asset_id,
        score=args.score,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("pool", event, backend_name))
    return 0


# ---------------------------------------------------------------------------
# Handler: arrangement (2 verbs)
# ---------------------------------------------------------------------------


def cmd_arrangement_set(args: argparse.Namespace) -> int:
    session = _require_session()
    from_json_path = Path(args.from_json).expanduser().resolve()
    if not from_json_path.is_file():
        raise TimelineEditError(f"arrangement JSON file not found: {from_json_path}")
    try:
        arrangement_data = json.loads(from_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TimelineEditError(f"--from-json must contain valid JSON: {exc.msg}") from exc
    if not isinstance(arrangement_data, dict):
        raise TimelineEditError("arrangement JSON file must contain a JSON object")
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = arrangement_edits.arrangement_replace(
        session.project,
        args.slug,
        arrangement=arrangement_data,
        actor=_timeline_actor_from_session(session),
        **extra,
    )
    print(_edit_success("arrangement", event, backend_name))
    return 0


def cmd_arrangement_show(args: argparse.Namespace) -> int:
    session = _require_session()
    arrangement = crud.get_arrangement(session.project, args.slug)
    if arrangement is None:
        data = crud.show_timeline(session.project, args.slug)
        if data is None:
            print(f"timeline '{args.slug}' not found", file=sys.stderr)
            return 1
    print(json.dumps(arrangement, indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# Handler: history (m7)
# ---------------------------------------------------------------------------


def _redact_actor(actor: TimelineActor) -> str:
    """Return a safe display string for an actor (no via/session/token)."""
    if actor.display:
        return actor.display
    return actor.id


def _format_history_row(version: int, event: TimelineEvent, backend_name: str) -> str:
    """Format one event row for the history table."""
    actor_display = _redact_actor(event.actor)
    return (
        f"  v{version:<6} {event.event_id}  "
        f"kind={event.kind:<28}  actor={actor_display}"
    )


def cmd_history(args: argparse.Namespace) -> int:
    """Read and pretty-print the event history of a timeline."""
    session = _require_session()
    project_slug = session.project

    from .observability import resolve_timeline_target
    from .eventlog import select_timeline_backend

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        print(f"timelines: {exc}", file=sys.stderr)
        return 1

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    events = backend.read_events(
        after=getattr(args, "since_event_id", None),
        limit=getattr(args, "limit", 50),
    )

    backend_label = backend.backend_name()

    if not events:
        print(f"(no events — backend={backend_label}, timeline={target.timeline_id})")
        return 0

    print(f"Backend:    {backend_label}")
    print(f"Timeline:   {target.timeline_id}  (slug: {target.slug})")
    print(f"Event count in this page: {len(events)}")
    print()

    # Determine starting version: if --since was given, find its index.
    if getattr(args, "since_event_id", None):
        all_events = backend.read_events()
        base_idx = next(
            (i for i, e in enumerate(all_events) if e.event_id == args.since_event_id),
            None,
        )
        base_version = (base_idx + 1) if base_idx is not None else 0
    else:
        base_version = 0

    for i, event in enumerate(events, start=1):
        version = base_version + i
        print(_format_history_row(version, event, backend_label))

    return 0


# ---------------------------------------------------------------------------
# Handler: diff (m7)
# ---------------------------------------------------------------------------


def _summarize_event_payload(event: TimelineEvent) -> str:
    """Produce a short operation-level summary of an event's payload."""
    payload = event.payload
    if isinstance(payload, dict):
        # Show a few key fields
        keys = sorted(payload.keys())
        if len(keys) <= 4:
            brief = {k: payload[k] for k in keys}
        else:
            brief = {k: payload[k] for k in keys[:4]}
            brief["..."] = f"+{len(keys) - 4} more fields"
        try:
            return json.dumps(brief, default=str)
        except Exception:
            return str(brief)
    return str(payload)


def cmd_diff(args: argparse.Namespace) -> int:
    """Semantic diff between two events in a timeline."""
    session = _require_session()
    project_slug = session.project

    from .observability import resolve_timeline_target
    from .eventlog import select_timeline_backend
    from .projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        print(f"timelines: {exc}", file=sys.stderr)
        return 1

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    all_events = backend.read_events()

    # Find from/to indices
    from_idx: int | None = None
    to_idx: int | None = None
    for i, event in enumerate(all_events):
        if event.event_id == args.from_event_id:
            from_idx = i
        if event.event_id == args.to_event_id:
            to_idx = i

    if from_idx is None:
        print(
            f"timelines: event '{args.from_event_id}' not found in timeline '{target.slug}'",
            file=sys.stderr,
        )
        return 1
    if to_idx is None:
        print(
            f"timelines: event '{args.to_event_id}' not found in timeline '{target.slug}'",
            file=sys.stderr,
        )
        return 1

    from_event = all_events[from_idx]
    to_event = all_events[to_idx]

    print(f"Diff:  {from_event.event_id}  →  {to_event.event_id}")
    print(f"Timeline: {target.timeline_id}  (slug: {target.slug})")
    print(f"Backend:  {backend.backend_name()}")
    print()

    print("From event:")
    print(f"  kind:    {from_event.kind}")
    print(f"  actor:   {_redact_actor(from_event.actor)}")
    print(f"  ts:      {from_event.ts}")
    print(f"  payload: {_summarize_event_payload(from_event)}")
    print()
    print("To event:")
    print(f"  kind:    {to_event.kind}")
    print(f"  actor:   {_redact_actor(to_event.actor)}")
    print(f"  ts:      {to_event.ts}")
    print(f"  payload: {_summarize_event_payload(to_event)}")
    print()

    # Show intervening events as operation-level summaries
    if to_idx - from_idx > 1:
        print(f"Intervening events ({to_idx - from_idx - 1}):")
        for i in range(from_idx + 1, to_idx):
            ev = all_events[i]
            print(
                f"  [{i + 1}] {ev.event_id}  kind={ev.kind}  "
                f"actor={_redact_actor(ev.actor)}"
            )
        print()

    if getattr(args, "with_state", False):
        try:
            from_state = replay_projection(backend, stop_at_event_id=from_event.event_id)
        except Exception as exc:
            print(f"timelines: failed to project state at from event: {exc}", file=sys.stderr)
            return 2
        try:
            to_state = replay_projection(backend, stop_at_event_id=to_event.event_id)
        except Exception as exc:
            print(f"timelines: failed to project state at to event: {exc}", file=sys.stderr)
            return 2

        print("Projected state at FROM event:")
        print(json.dumps(from_state, indent=2, default=str))
        print()
        print("Projected state at TO event:")
        print(json.dumps(to_state, indent=2, default=str))

    return 0


# ---------------------------------------------------------------------------
# Handler: audit (m7)
# ---------------------------------------------------------------------------


def _diff_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return keys that differ between two dicts (top-level only)."""
    keys = sorted(set(before.keys()) | set(after.keys()))
    diffs: list[str] = []
    for k in keys:
        if before.get(k) != after.get(k):
            diffs.append(k)
    return diffs


def cmd_audit(args: argparse.Namespace) -> int:
    """Verify event chain integrity and projection parity."""
    session = _require_session()
    project_slug = session.project

    from .observability import read_ops_log, resolve_timeline_target
    from .eventlog import select_timeline_backend
    from .projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        print(f"timelines: {exc}", file=sys.stderr)
        return 1

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    issues: list[str] = []

    # 1. Verify hash chain
    verification = backend.verify_chain()
    chain_ok = verification.ok
    chain_checked = verification.checked_events
    chain_error = verification.error

    # 2. Head
    head_ok = True
    head_error: str | None = None
    try:
        head = backend.head()
    except Exception as exc:
        head_ok = False
        head_error = str(exc)

    # 3. Projection parity: pure replay vs on-disk assembly.json
    projection_parity_ok: bool | None = None
    projection_parity_error: str | None = None
    try:
        replayed = replay_projection(backend)
    except Exception as exc:
        projection_parity_ok = False
        projection_parity_error = f"replay failed: {exc}"
    else:
        assembly_path = target.timeline_home / "assembly.json"
        if assembly_path.is_file():
            try:
                existing = read_json(assembly_path)
            except Exception as exc:
                projection_parity_ok = False
                projection_parity_error = f"failed to read assembly.json: {exc}"
            else:
                if isinstance(existing, dict):
                    existing_assembly = existing.get("assembly", existing)
                else:
                    existing_assembly = existing
                if existing_assembly != replayed:
                    projection_parity_ok = False
                    diff_keys = _diff_keys(
                        existing_assembly if isinstance(existing_assembly, dict) else {},
                        replayed if isinstance(replayed, dict) else {},
                    )
                    projection_parity_error = (
                        f"assembly.json does not match replay; "
                        f"differing keys: {diff_keys if diff_keys else '(structural mismatch)'}"
                    )
                else:
                    projection_parity_ok = True
        else:
            # No derived blob exists — parity check is not applicable.
            projection_parity_ok = None

    # 4. Ops log
    ops_entries = None
    ops_log_error: str | None = None
    if getattr(args, "include_ops", False):
        ops_entries = read_ops_log(target.timeline_home)
        if ops_entries is None:
            ops_log_error = "no operational failure logs"

    # --- Print results ---
    print(f"Audit for timeline '{target.slug}'")
    print(f"  Backend:     {backend.backend_name()}")
    print(f"  Timeline ID: {target.timeline_id}")
    print()

    # Chain
    status_chain = "OK" if chain_ok else "FAIL"
    print(f"  Hash chain:  {status_chain}  (checked {chain_checked} events)")
    if chain_error:
        issues.append(f"chain: {chain_error}")
        print(f"    Error: {chain_error}")

    # Head
    status_head = "OK" if head_ok else "FAIL"
    print(f"  Head:        {status_head}")
    if head_error:
        issues.append(f"head: {head_error}")
        print(f"    Error: {head_error}")
    elif head_ok:
        print(f"    timeline_id={head.timeline_id}, version={head.version}, "
              f"events={head.event_count}, last={head.last_event_id}")

    # Projection parity
    if projection_parity_ok is None:
        print(f"  Projection:  N/A  (no assembly.json to compare)")
    elif projection_parity_ok:
        print(f"  Projection:  OK  (assembly.json matches replay)")
    else:
        issues.append(f"projection: {projection_parity_error}")
        print(f"  Projection:  MISMATCH")
        if projection_parity_error:
            print(f"    {projection_parity_error}")

    # Ops log
    if ops_entries is not None:
        print(f"  Ops log:     {len(ops_entries)} entries")
        for entry in ops_entries:
            print(f"    - [{entry.ts}] event={entry.event_id} kind={entry.kind}: {entry.error}")
    elif ops_log_error is not None:
        print(f"  Ops log:     ({ops_log_error})")

    print()

    if issues:
        print(f"Summary: {len(issues)} issue(s) found")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("Summary: all checks passed")
    return 0


# ---------------------------------------------------------------------------
# Handler: preview (m7)
# ---------------------------------------------------------------------------


def cmd_preview(args: argparse.Namespace) -> int:
    """Project a past state at a specific event."""
    session = _require_session()
    project_slug = session.project

    from .observability import resolve_timeline_target
    from .eventlog import select_timeline_backend
    from .projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        print(f"timelines: {exc}", file=sys.stderr)
        return 1

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    try:
        state = replay_projection(backend, stop_at_event_id=args.at_event_id)
    except Exception as exc:
        print(f"timelines: failed to project state at '{args.at_event_id}': {exc}", file=sys.stderr)
        return 2

    out_path_raw = getattr(args, "out_path", None)
    if out_path_raw:
        out_path = Path(out_path_raw).expanduser().resolve()
        timeline_home_resolved = target.timeline_home.resolve()

        # Guard: reject --out paths inside the timeline home.
        try:
            out_path.relative_to(timeline_home_resolved)
        except ValueError:
            pass  # not inside timeline home — ok
        else:
            print(
                f"timelines: --out path '{out_path_raw}' is inside the timeline home; "
                f"refusing to overwrite canonical files",
                file=sys.stderr,
            )
            return 2

        from astrid.core.project.jsonio import write_json_atomic

        write_json_atomic(out_path, state)
        print(f"Projected state written to {out_path}")
    else:
        print(json.dumps(state, indent=2, default=str))

    return 0


# ---------------------------------------------------------------------------
# Handler: who-edited (m7)
# ---------------------------------------------------------------------------


def cmd_who_edited(args: argparse.Namespace) -> int:
    """Show actor rollup for a timeline."""
    session = _require_session()
    project_slug = session.project

    from .observability import resolve_timeline_target
    from .eventlog import select_timeline_backend

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        print(f"timelines: {exc}", file=sys.stderr)
        return 1

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    events = backend.read_events()

    if not events:
        print(f"(no events — backend={backend.backend_name()}, timeline={target.timeline_id})")
        return 0

    # Actor rollup: group by actor.id, count events by kind.
    rollup: dict[str, dict[str, Any]] = {}
    for event in events:
        actor = event.actor
        actor_key = actor.id
        if actor_key not in rollup:
            rollup[actor_key] = {
                "actor_id": actor.id,
                "actor_display": _redact_actor(actor),
                "kinds": {},
                "total": 0,
            }
        entry = rollup[actor_key]
        entry["kinds"][event.kind] = entry["kinds"].get(event.kind, 0) + 1
        entry["total"] += 1

    sorted_entries = sorted(rollup.values(), key=lambda e: e["total"], reverse=True)

    print(f"Actor rollup for timeline '{target.slug}'")
    print(f"  Backend:     {backend.backend_name()}")
    print(f"  Timeline ID: {target.timeline_id}")
    print(f"  Total actors: {len(sorted_entries)}")
    print()

    for entry in sorted_entries:
        print(f"  {entry['actor_display']}  (id: {entry['actor_id']})")
        print(f"    total events: {entry['total']}")
        for kind, count in sorted(entry["kinds"].items()):
            print(f"      {kind}: {count}")
        print()

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


def _add_expected_version_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--expected-version",
        type=int,
        dest="expected_version",
        default=None,
        help="Require the current eventlog version to match before applying the mutation.",
    )


def _expected_version_kwargs(args: argparse.Namespace) -> dict[str, int]:
    expected_version = getattr(args, "expected_version", None)
    if expected_version is None:
        return {}
    return {"expected_version": expected_version}


def _timeline_actor_from_session(session: Any) -> TimelineActor:
    agent_id = getattr(session, "agent_id", "") or "unknown-agent"
    session_id = getattr(session, "id", "") or "unknown-session"
    return TimelineActor(
        type="agent",
        id=f"{agent_id}:{session_id}",
        display=agent_id,
    )
