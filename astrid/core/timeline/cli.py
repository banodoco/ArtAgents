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

from astrid.contracts.errors import AstridError, coerce_astrid_error
from astrid.core.cli_choices import (
    AstridArgumentError,
    RecoverableArgumentParser,
    add_choice_arg,
    add_kind_arg,
)
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
from .kinds import default_transition_kind
from .paths import assembly_identity_path, find_timeline_by_slug
from .projection import ErasedPayloadProjectionError, ProjectionError

_SESSION_GATE_HINT = (
    "A timeline command requires a bound session. "
    "Run 'astrid attach <project>' first."
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except AstridArgumentError as exc:
        raise AstridError(str(exc)) from exc
    except (crud.TimelineCrudError, TimelineEditError, SessionBindingError, EventLogError) as exc:
        raise coerce_astrid_error(exc) from exc
    except ErasedPayloadProjectionError as exc:
        raise AstridError(f"{exc} (erased payload)") from exc
    except (ProjectionError, ValueError) as exc:
        raise AstridError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = RecoverableArgumentParser(
        prog="python3 -m astrid timelines",
        description="Create, inspect, and manage project timelines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- ls ---
    ls_parser = subparsers.add_parser("ls", aliases=["list"], help="List timelines in the current project.")
    ls_parser.add_argument(
        "--project",
        help="Project slug (required when no session is bound).",
    )
    ls_parser.add_argument(
        "--include-tombstoned",
        action="store_true",
        help="Include tombstoned timelines for audit views.",
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
    add_kind_arg(clip_add, "--kind", catalog="clip", required=True, help="Clip kind.")
    clip_add.add_argument("--asset", required=True, help="Asset identifier.")
    clip_add.add_argument(
        "--track",
        "--track-id",
        required=True,
        dest="track_id",
        help="Existing target track identifier for the clip.",
    )
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

    # clip retrack
    clip_retrack = clip_subs.add_parser("retrack", help="Move a clip to a different track.")
    clip_retrack.add_argument("slug", help="Timeline slug.")
    clip_retrack.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_retrack.add_argument(
        "--track",
        "--track-id",
        required=True,
        dest="track_id",
        help="Existing target track identifier.",
    )
    _add_expected_version_arg(clip_retrack)
    clip_retrack.set_defaults(handler=cmd_clip_retrack)

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
    add_kind_arg(trans_set, "--kind", catalog="transition", default=default_transition_kind(), help="Transition kind.")
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
    add_kind_arg(track_add_p, "--kind", catalog="track", required=True, help="Track kind.")
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
    arr_set_p = arr_subs.add_parser(
        "set",
        help="Retired: arrangement replacement is migration-only legacy.",
    )
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

    # --- migrate-events ---
    migrate_parser = subparsers.add_parser(
        "migrate-events",
        help="Migrate legacy timeline data into event streams.",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview migration without writing (default).",
    )
    migrate_parser.add_argument(
        "--apply",
        action="store_true",
        dest="apply",
        default=False,
        help="Actually write event-stream imports.",
    )
    project_or_all = migrate_parser.add_mutually_exclusive_group(required=True)
    project_or_all.add_argument(
        "--project",
        dest="project_slug",
        help="Migrate timelines for one project slug.",
    )
    project_or_all.add_argument(
        "--all-projects",
        action="store_true",
        dest="all_projects",
        help="Migrate timelines across all discovered projects.",
    )
    migrate_parser.add_argument(
        "--json",
        dest="json_out",
        action="store_true",
        help="Emit structured JSON instead of pretty-print.",
    )
    migrate_parser.set_defaults(handler=cmd_migrate_events)

    # --- push (m9) ---
    push_parser = subparsers.add_parser(
        "push", help="Push a local timeline to Supabase via event-log replay."
    )
    push_parser.add_argument(
        "slug_or_id", help="Local timeline slug, ULID, or event-stream UUID."
    )
    add_choice_arg(push_parser, "--to", values=("supabase",), dest="to_backend", required=True, help="Destination backend (only 'supabase' in v1).")
    push_parser.add_argument(
        "--project",
        help="Project slug (required when no session is bound).",
    )
    push_parser.set_defaults(handler=cmd_push)

    # --- pull (m9) ---
    pull_parser = subparsers.add_parser(
        "pull", help="Pull a Supabase timeline to a local destination via event-log replay."
    )
    pull_parser.add_argument(
        "slug_or_id", help="Remote timeline slug or event-stream UUID on Supabase."
    )
    add_choice_arg(pull_parser, "--from", values=("supabase",), dest="from_backend", required=True, help="Source backend (only 'supabase' in v1).")
    pull_parser.add_argument(
        "--project",
        required=True,
        help="Project slug for the local destination.",
    )
    pull_parser.add_argument(
        "--into",
        dest="into_slug",
        default=None,
        help="Pull into an existing local timeline with this slug.",
    )
    pull_parser.add_argument(
        "--as",
        dest="create_as_slug",
        default=None,
        help="Create a new local timeline with this slug (requires --create).",
    )
    pull_parser.add_argument(
        "--create",
        action="store_true",
        default=False,
        help="Create a new local timeline as the pull destination.",
    )
    pull_parser.set_defaults(handler=cmd_pull)

    # --- branch (m9) ---
    branch_parser = subparsers.add_parser(
        "branch", help="Manage timeline branches."
    )
    branch_subs = branch_parser.add_subparsers(dest="branch_command", required=True)

    # branch create
    branch_create = branch_subs.add_parser(
        "create", help="Create a branch from a source timeline at a specific event."
    )
    branch_create.add_argument(
        "source_slug_or_id", help="Source timeline slug, ULID, or UUID."
    )
    branch_create.add_argument(
        "branch_slug", help="Slug for the new branch timeline."
    )
    branch_create.add_argument(
        "--from",
        required=True,
        dest="from_event_id",
        help="Source event ID to branch from (anchor point).",
    )
    branch_create.add_argument(
        "--reason",
        default="",
        help="Human-readable reason for the branch.",
    )
    branch_create.set_defaults(handler=cmd_branch_create)

    # branch list
    branch_list = branch_subs.add_parser(
        "list", help="List branches of a source timeline."
    )
    branch_list.add_argument(
        "source_slug_or_id", help="Source timeline slug, ULID, or UUID."
    )
    branch_list.set_defaults(handler=cmd_branch_list)

    # --- undo (m9) ---
    undo_parser = subparsers.add_parser(
        "undo", help="Undo the latest undoable event on a timeline."
    )
    undo_parser.add_argument(
        "slug", help="Timeline slug."
    )
    add_choice_arg(undo_parser, "--from", values=("supabase",), dest="from_backend", default=None, help="Backend to undo on (default: local_fs).")
    undo_parser.add_argument(
        "--project",
        help="Project slug (required when no session is bound).",
    )
    undo_parser.set_defaults(handler=cmd_undo)

    # --- mass-undo (m9) ---
    mass_undo_parser = subparsers.add_parser(
        "mass-undo", help="Preview-first mass undo of events matching filter criteria."
    )
    mass_undo_parser.add_argument(
        "slug", help="Timeline slug."
    )
    mass_undo_parser.add_argument(
        "--since",
        dest="ts_since",
        default=None,
        help="Timestamp ISO-8601 lower bound (inclusive) — only undo events at or after this time.",
    )
    mass_undo_parser.add_argument(
        "--actor",
        dest="actor_id",
        default=None,
        help="Exact actor ID match.",
    )
    mass_undo_parser.add_argument(
        "--actor-prefix",
        dest="actor_id_prefix",
        default=None,
        help="Actor ID prefix match.",
    )
    mass_undo_parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Confirm mass undo (required to actually write).",
    )
    add_choice_arg(mass_undo_parser, "--from", values=("supabase",), dest="from_backend", default=None, help="Backend to undo on (default: local_fs).")
    mass_undo_parser.add_argument(
        "--project",
        help="Project slug (required when no session is bound).",
    )
    mass_undo_parser.set_defaults(handler=cmd_mass_undo)

    # --- erase (m9) ---
    erase_parser = subparsers.add_parser(
        "erase", help="Erase (redact) event payloads matching a selector."
    )
    erase_parser.add_argument(
        "slug", help="Timeline slug."
    )
    erase_parser.add_argument(
        "--event-ids",
        dest="event_ids_raw",
        default=None,
        help="Comma-separated event IDs (ULIDs) to erase.",
    )
    erase_parser.add_argument(
        "--kind",
        dest="kind_allowlist_raw",
        default=None,
        help="Comma-separated event kind allowlist (e.g. 'clip.added,clip.removed').",
    )
    erase_parser.add_argument(
        "--actor",
        dest="actor_id",
        default=None,
        help="Exact actor ID match.",
    )
    erase_parser.add_argument(
        "--actor-prefix",
        dest="actor_id_prefix",
        default=None,
        help="Actor ID prefix match.",
    )
    erase_parser.add_argument(
        "--after",
        dest="ts_after",
        default=None,
        help="Timestamp ISO-8601 lower bound (inclusive).",
    )
    erase_parser.add_argument(
        "--before",
        dest="ts_before",
        default=None,
        help="Timestamp ISO-8601 upper bound (inclusive).",
    )
    erase_parser.add_argument(
        "--reason",
        required=True,
        help="Human-readable reason for the erasure.",
    )
    erase_parser.add_argument(
        "--policy-ref",
        dest="policy_ref",
        default=None,
        help="Optional policy reference for the erasure.",
    )
    erase_parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Actually perform the erasure (preview-only without this flag).",
    )
    erase_parser.set_defaults(handler=cmd_erase)

    # --- recover (m9) ---
    recover_parser = subparsers.add_parser(
        "recover", help="Recover a timeline to a known-good anchor event."
    )
    recover_parser.add_argument(
        "slug", help="Timeline slug."
    )
    recover_parser.add_argument(
        "--at",
        required=True,
        dest="at_event_id",
        help="Event ID (ULID) to recover to (anchor point).",
    )
    recover_parser.add_argument(
        "--reason",
        required=True,
        help="Human-readable reason for the recovery.",
    )
    add_choice_arg(recover_parser, "--from", values=("supabase",), dest="from_backend", default=None, help="Backend to recover on (default: local_fs).")
    recover_parser.add_argument(
        "--project",
        help="Project slug (required when no session is bound).",
    )
    recover_parser.set_defaults(handler=cmd_recover)

    # --- branches (m9) ---
    branches_parser = subparsers.add_parser(
        "branches", help="List branches of a timeline (alias for 'branch list')."
    )
    branches_parser.add_argument(
        "source_slug_or_id", help="Source timeline slug, ULID, or UUID."
    )
    branches_parser.set_defaults(handler=cmd_branch_list)

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
        raise AstridError(
            f"timeline '{args.slug}' not found",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        )

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

        def _add_bytes(data: bytes, rel: str) -> None:
            dst = tmpdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
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
        for run_id in _timeline_contributing_runs(proj_root, manifest.contributing_runs, include_aborted=include_aborted):
            run_root = runs_dir / run_id
            if not run_root.is_dir():
                continue

            # Copy the run's own plan snapshot. Older runs may only have the
            # initial plan embedded in events.jsonl; export that snapshot
            # rather than the mutable project-level plan cache.
            plan_path = run_root / "plan.json"
            if plan_path.is_file():
                _add_file(plan_path, f"runs/{run_id}/plan.json")
            else:
                plan_payload = _run_initial_plan_payload(run_root / "events.jsonl")
                if plan_payload is not None:
                    data = json.dumps(
                        plan_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    _add_bytes(
                        data,
                        f"runs/{run_id}/plan.json",
                    )

            # Copy events.jsonl
            events_path = run_root / "events.jsonl"
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


def _run_initial_plan_payload(events_path: Path) -> dict[str, object] | None:
    if not events_path.is_file():
        return None
    from astrid.core.task.events import read_events

    for event in read_events(events_path):
        if event.get("kind") == "plan_initialized" and isinstance(
            event.get("plan"), dict
        ):
            return event["plan"]
    return None


# ---------------------------------------------------------------------------
# Handler: cost (Sprint 5b)
# ---------------------------------------------------------------------------


def cmd_cost(args: argparse.Namespace) -> int:
    """Aggregate cost across all contributing runs in a timeline."""
    session = _require_session()
    data = crud.show_timeline(session.project, args.slug)
    if data is None:
        raise AstridError(
            f"timeline '{args.slug}' not found",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        )

    manifest = data["manifest"]
    proj_root = project_dir(session.project)
    runs_dir = proj_root / "runs"
    include_aborted = bool(getattr(args, "include_aborted", False))

    # Aggregate costs across all contributing runs
    by_source: dict[str, dict[str, Any]] = {}
    grand_total = 0.0
    run_ids = _timeline_contributing_runs(
        proj_root,
        manifest.contributing_runs,
        include_aborted=include_aborted,
    )

    for run_id in run_ids:
        events_path = runs_dir / run_id / "events.jsonl"
        events = read_events(events_path)
        cost_summary = _cost_by_source(events)
        grand_total += _merge_cost_summaries(by_source, cost_summary)

    json_out = bool(getattr(args, "json_out", False))
    if json_out:
        payload: dict[str, Any] = {
            "slug": args.slug,
            "project": session.project,
            "contributing_runs": len(run_ids),
            "total_runs_in_manifest": len(manifest.contributing_runs),
            "include_aborted": include_aborted,
            "grand_total": round(grand_total, 6),
            "by_source": by_source,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Cost rollup for timeline '{args.slug}' ({len(run_ids)} contributing runs):")
    print()
    if not by_source:
        print("  (no cost data)")
    else:
        for source in sorted(by_source):
            amt = float(by_source[source].get("amount", 0.0))
            print(f"  {source:<20} ${amt:>10.4f}")
    print(f"  {'─' * 32}")
    print(f"  {'TOTAL':<20} ${grand_total:>10.4f}")
    return 0


def _timeline_contributing_runs(
    proj_root: Path,
    run_ids: list[str] | tuple[str, ...],
    *,
    include_aborted: bool,
) -> list[str]:
    runs_dir = proj_root / "runs"
    selected: list[str] = []
    seen: set[str] = set()
    for run_id in run_ids:
        if run_id in seen:
            continue
        seen.add(run_id)
        run_root = runs_dir / run_id
        if not run_root.is_dir():
            continue
        events_path = run_root / "events.jsonl"
        if events_path.exists():
            events = read_events(events_path)
            if _run_status(events) == "aborted" and not include_aborted:
                continue
        selected.append(run_id)
    return selected


def _merge_cost_summaries(
    target: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
) -> float:
    added_total = 0.0
    for source, info in incoming.items():
        if not isinstance(info, dict):
            continue
        amount = float(info.get("amount", 0.0))
        currency = str(info.get("currency", "USD"))
        bucket = target.setdefault(
            source,
            {"amount": 0.0, "currency": currency, "source": source},
        )
        bucket["amount"] = round(float(bucket.get("amount", 0.0)) + amount, 6)
        bucket["currency"] = currency
        bucket["source"] = source
        added_total += amount
    return added_total


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
        track_id=getattr(args, "track_id", None),
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


def cmd_clip_retrack(args: argparse.Namespace) -> int:
    session = _require_session()
    backend_name = _resolve_clip_backend_name(session.project, args.slug)
    extra = _expected_version_kwargs(args)
    event = clip_edits.retrack_clip(
        session.project,
        args.slug,
        clip_id=args.clip_id,
        track_id=args.track_id,
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
    _require_session()
    raise TimelineEditError(
        "arrangement set is retired: arrangement.replaced is migration-only "
        "legacy. Use timeline.config_replaced with a raw TimelineConfig for "
        "canonical full-timeline writes."
    )


def cmd_arrangement_show(args: argparse.Namespace) -> int:
    session = _require_session()
    arrangement = crud.get_arrangement(session.project, args.slug)
    if arrangement is None:
        data = crud.show_timeline(session.project, args.slug)
        if data is None:
            raise AstridError(
                f"timeline '{args.slug}' not found",
                recovery_command="astrid timelines ls",
                state_snapshot={"timeline": args.slug},
            )
    print(json.dumps(arrangement, indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# Handler: migrate-events (m8)
# ---------------------------------------------------------------------------


def cmd_migrate_events(args: argparse.Namespace) -> int:
    """Run timeline event-stream migration (dry-run or --apply).

    Supports --project <slug> or --all-projects.  --dry-run is the default;
    --apply actually writes event-stream imports.  --json emits structured
    output instead of pretty-print.

    Returns nonzero on parity failures or unreadable source blobs.
    """
    from .eventlog.local_fs import LocalFsBackend
    from .events.schema import TimelineActor
    from .migration import (
        MigrationResult,
        SkippedTimeline,
        discover_projects_for_migration,
        discover_timelines_for_project,
        import_from_legacy_local,
    )

    write_mode = bool(getattr(args, "apply", False))
    json_out = bool(getattr(args, "json_out", False))
    all_projects = bool(getattr(args, "all_projects", False))
    project_slug: str | None = getattr(args, "project_slug", None)

    # --- Resolve project list ---
    if all_projects:
        slugs = discover_projects_for_migration()
    elif project_slug:
        slugs = [project_slug]
    else:
        raise AstridError(
            "timelines migrate-events: must specify --project or --all-projects",
            valid_options=["--project <slug>", "--all-projects"],
            recovery_command="astrid timelines migrate-events --project <slug>",
        )

    if not slugs:
        print("(no projects discovered)")
        return 0

    result = MigrationResult()

    for slug in slugs:
        timelines = discover_timelines_for_project(slug)
        for ulid, classification in timelines:
            if classification == "already_event_sourced":
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason="Already event-sourced — skipping",
                        classification=classification,
                    )
                )
                continue

            if classification == "malformed_incomplete":
                result.malformed.append(ulid)
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason="Malformed or incomplete timeline directory",
                        classification=classification,
                    )
                )
                continue

            # classification == "legacy_local"
            if not write_mode:
                # Dry-run: just report what would happen
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason="Would import (dry-run)",
                        classification=classification,
                    )
                )
                continue

            # --apply mode: actually import
            from astrid.core.timeline.paths import timeline_dir

            tdir = timeline_dir(slug, ulid)
            backend = LocalFsBackend(timeline_home=tdir, timeline_id=ulid)
            actor = TimelineActor(type="agent", id="cli:migrate-events", display="migrate-events")

            import_result = import_from_legacy_local(
                backend=backend,
                timeline_home=tdir,
                actor=actor,
            )

            if import_result.get("imported"):
                result.imported.append(ulid)
                if not import_result.get("parity_ok"):
                    from .migration import ParityFailure
                    result.parity_failures.append(
                        ParityFailure(
                            project_slug=slug,
                            timeline_ulid=ulid,
                            source_hash="",
                            projected_hash="",
                            detail=import_result.get("detail", "Parity check failed"),
                        )
                    )
            else:
                result.skipped.append(
                    SkippedTimeline(
                        project_slug=slug,
                        timeline_ulid=ulid,
                        reason=import_result.get("detail", "Import skipped"),
                        classification=classification,
                    )
                )

    # --- Output ---
    if json_out:
        output = {
            "imported_count": len(result.imported),
            "skipped_count": len(result.skipped),
            "parity_failure_count": len(result.parity_failures),
            "malformed_count": len(result.malformed),
            "imported": result.imported,
            "skipped": [
                {
                    "project_slug": s.project_slug,
                    "timeline_ulid": s.timeline_ulid,
                    "reason": s.reason,
                    "classification": s.classification,
                }
                for s in result.skipped
            ],
            "parity_failures": [
                {
                    "project_slug": f.project_slug,
                    "timeline_ulid": f.timeline_ulid,
                    "detail": f.detail,
                }
                for f in result.parity_failures
            ],
            "malformed": result.malformed,
            "ok": result.ok,
        }
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    else:
        mode_label = "dry-run" if not write_mode else "applied"
        print(f"Migration {mode_label} — {len(result.imported)} imported, "
              f"{len(result.skipped)} skipped, "
              f"{len(result.parity_failures)} parity failures, "
              f"{len(result.malformed)} malformed")

        if result.skipped:
            print("\nSkipped:")
            for s in result.skipped:
                print(f"  [{s.project_slug}] {s.timeline_ulid or '?'}: {s.reason}")

        if result.parity_failures:
            print(f"\nParity failures ({len(result.parity_failures)}):")
            for f in result.parity_failures:
                print(f"  [{f.project_slug}] {f.timeline_ulid}: {f.detail}")

        if result.malformed:
            print(f"\nMalformed ({len(result.malformed)}):")
            for ulid in result.malformed:
                print(f"  {ulid}")

        if result.imported:
            print(f"\nImported ({len(result.imported)}):")
            for ulid in result.imported:
                print(f"  {ulid}")

    return 0 if result.ok else 1


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

    from .eventlog import select_timeline_backend
    from .observability import resolve_timeline_target

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

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

    from .eventlog import select_timeline_backend
    from .observability import resolve_timeline_target
    from .projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

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
        raise AstridError(
            f"timelines: event '{args.from_event_id}' not found in timeline '{target.slug}'",
            recovery_command=f"astrid timelines history {args.slug_or_id}",
            state_snapshot={"timeline": target.slug, "event_id": args.from_event_id},
        )
    if to_idx is None:
        raise AstridError(
            f"timelines: event '{args.to_event_id}' not found in timeline '{target.slug}'",
            recovery_command=f"astrid timelines history {args.slug_or_id}",
            state_snapshot={"timeline": target.slug, "event_id": args.to_event_id},
        )

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
            raise AstridError(
                f"timelines: failed to project state at from event: {exc}",
                recovery_command=f"astrid timelines audit {args.slug_or_id}",
                state_snapshot={"timeline": target.slug, "event_id": from_event.event_id},
            ) from exc
        try:
            to_state = replay_projection(backend, stop_at_event_id=to_event.event_id)
        except Exception as exc:
            raise AstridError(
                f"timelines: failed to project state at to event: {exc}",
                recovery_command=f"astrid timelines audit {args.slug_or_id}",
                state_snapshot={"timeline": target.slug, "event_id": to_event.event_id},
            ) from exc

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

    from .eventlog import select_timeline_backend
    from .observability import read_ops_log, resolve_timeline_target
    from .projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

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
        print("  Projection:  N/A  (no assembly.json to compare)")
    elif projection_parity_ok:
        print("  Projection:  OK  (assembly.json matches replay)")
    else:
        issues.append(f"projection: {projection_parity_error}")
        print("  Projection:  MISMATCH")
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

    from .eventlog import select_timeline_backend
    from .observability import resolve_timeline_target
    from .projection import replay_projection

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    try:
        state = replay_projection(backend, stop_at_event_id=args.at_event_id)
    except Exception as exc:
        raise AstridError(
            f"timelines: failed to project state at '{args.at_event_id}': {exc}",
            recovery_command=f"astrid timelines audit {args.slug_or_id}",
            state_snapshot={"timeline": args.slug_or_id, "event_id": args.at_event_id},
        ) from exc

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
            raise AstridError(
                f"timelines: --out path '{out_path_raw}' is inside the timeline home; "
                f"refusing to overwrite canonical files",
                recovery_command="choose an --out path outside the timeline home",
                state_snapshot={"out": out_path_raw, "timeline_home": timeline_home_resolved},
            )

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

    from .eventlog import select_timeline_backend
    from .observability import resolve_timeline_target

    try:
        target = resolve_timeline_target(project_slug, args.slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

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
# Handler: push (m9)
# ---------------------------------------------------------------------------


def cmd_push(args: argparse.Namespace) -> int:
    """Push a local timeline to Supabase via event-log replay."""
    session = _resolve_optional_session(args)
    project_slug = _resolve_project_slug(args, session)

    from .transfer import push_timeline

    try:
        result = push_timeline(
            project_slug,
            args.slug_or_id,
            destination_actor=_timeline_actor_from_session(session) if session else None,
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines push: {exc}",
            recovery_command="astrid timelines push <slug-or-id>",
            state_snapshot={"timeline": args.slug_or_id},
        ) from exc

    print(f"Push: {result.direction} {result.source_backend_name} → {result.destination_backend_name}")
    print(f"  source timeline: {result.source_timeline_id}")
    print(f"  destination timeline: {result.destination_timeline_id}")
    print(f"  scanned: {result.scanned}")
    print(f"  appended: {result.appended}")
    print(f"  skipped (idempotent): {result.skipped_idempotent}")
    print(f"  failed: {result.failed}")
    print(f"  destination version: {result.destination_version}")
    print(f"  projection regenerated: {result.projection_regenerated}")

    if result.failed > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Handler: pull (m9)
# ---------------------------------------------------------------------------


def cmd_pull(args: argparse.Namespace) -> int:
    """Pull a Supabase timeline to a local destination via event-log replay."""
    project_slug = args.project  # --project is required for pull

    from .transfer import pull_timeline

    try:
        result = pull_timeline(
            project_slug,
            args.slug_or_id,
            into=args.into_slug,
            create_as=args.create_as_slug,
            create=args.create,
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines pull: {exc}",
            recovery_command="astrid timelines pull --project <slug> <slug-or-id>",
            state_snapshot={"project": project_slug, "timeline": args.slug_or_id},
        ) from exc

    print(f"Pull: {result.direction} {result.source_backend_name} → {result.destination_backend_name}")
    print(f"  source timeline: {result.source_timeline_id}")
    print(f"  destination timeline: {result.destination_timeline_id}")
    print(f"  scanned: {result.scanned}")
    print(f"  appended: {result.appended}")
    print(f"  skipped (idempotent): {result.skipped_idempotent}")
    print(f"  failed: {result.failed}")
    print(f"  destination version: {result.destination_version}")
    print(f"  projection regenerated: {result.projection_regenerated}")

    if result.failed > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Handler: branch create (m9)
# ---------------------------------------------------------------------------


def cmd_branch_create(args: argparse.Namespace) -> int:
    """Create a branch timeline from a source timeline."""
    session = _require_session()

    from .branch import create_branch_timeline

    try:
        result = create_branch_timeline(
            session.project,
            args.source_slug_or_id,
            args.branch_slug,
            from_event_id=args.from_event_id,
            actor=_timeline_actor_from_session(session),
            reason=args.reason,
        )
    except (ValueError, ProjectionError) as exc:
        raise AstridError(
            f"timelines branch create: {exc}",
            recovery_command="astrid timelines branch create <source> <branch-slug>",
            state_snapshot={
                "source": args.source_slug_or_id,
                "branch": args.branch_slug,
            },
        ) from exc

    print(f"Branch created: {result.branch_slug}")
    print(f"  branch timeline ID: {result.branch_timeline_id}")
    print(f"  branch timeline ULID: {result.branch_timeline_ulid}")
    print(f"  anchor event: {result.anchor_event_id} (hash: {result.source_anchor_hash})")
    print(f"  seed event: {result.seed_event_id}")
    print(f"  source branched_from event: {result.source_branched_from_event_id}")
    print(f"  projection: clips={result.branch_projection_summary.get('clip_count', 0)}, "
          f"tracks={result.branch_projection_summary.get('track_count', 0)}")
    return 0


# ---------------------------------------------------------------------------
# Handler: branch list (m9)
# ---------------------------------------------------------------------------


def cmd_branch_list(args: argparse.Namespace) -> int:
    """List branches of a source timeline."""
    session = _require_session()

    from .branch import list_branches

    try:
        branches = list_branches(session.project, args.source_slug_or_id)
    except ValueError as exc:
        raise AstridError(
            f"timelines branch list: {exc}",
            recovery_command="astrid timelines branch list <source>",
            state_snapshot={"source": args.source_slug_or_id},
        ) from exc

    if not branches:
        print(f"(no branches for timeline '{args.source_slug_or_id}')")
        return 0

    print(f"Branches of '{args.source_slug_or_id}':")
    for b in branches:
        reason_str = f"  reason: {b['reason']}" if b.get("reason") else ""
        print(f"  - branch: {b['branch_timeline_id']}")
        print(f"    anchor: {b['anchor_event_id']}")
        print(f"    at: {b['ts']}")
        if reason_str:
            print(f"   {reason_str}")
    return 0


# ---------------------------------------------------------------------------
# Handler: undo (m9)
# ---------------------------------------------------------------------------


def cmd_undo(args: argparse.Namespace) -> int:
    """Undo the latest undoable event on a timeline."""
    session = _require_session()
    project_slug = session.project

    from .inverses import plan_inverses
    from .observability import resolve_timeline_target
    from .projection import regenerate_projection, replay_projection

    # Resolve the timeline
    try:
        target = resolve_timeline_target(project_slug, args.slug)
    except ValueError as exc:
        raise AstridError(
            f"timelines undo: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        ) from exc

    preferred_backend = getattr(args, "from_backend", None) or target.backend

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=preferred_backend,
    )

    # Verify chain before undoing
    verification = backend.verify_chain()
    if not verification.ok:
        raise AstridError(
            f"timelines undo: chain verification failed: "
            f"{verification.error or 'unknown error'}; refusing to undo",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "verification_error": verification.error},
        )

    # Get all events
    all_events = backend.read_events()
    if not all_events:
        raise AstridError(
            "timelines undo: no events in timeline",
            recovery_command=f"astrid timelines history {args.slug}",
            state_snapshot={"timeline": args.slug},
        )

    # Find the latest undoable event (skip lifecycle/ops by default)
    # Also skip erased events
    from astrid.core.timeline.events.schema import ErasedPayload

    from .inverses import _NON_REVERSIBLE_KINDS

    target_idx: int | None = None
    target_event = None
    for i in range(len(all_events) - 1, -1, -1):
        evt = all_events[i]
        # Skip lifecycle/ops events
        if evt.kind in _NON_REVERSIBLE_KINDS:
            continue
        # Skip already-erased events
        if isinstance(evt.payload, ErasedPayload):
            continue
        target_idx = i
        target_event = evt
        break

    if target_event is None or target_idx is None:
        print("timelines undo: no undoable events found (all are lifecycle/ops or erased)")
        return 0

    # Project before and after states
    before_events = all_events[:target_idx]  # events up to (not including) target
    after_events = all_events[: target_idx + 1]  # events up to and including target

    try:
        before_projection = replay_projection(backend, stop_at_event_id=before_events[-1].event_id) if before_events else {}
    except Exception as exc:
        raise AstridError(
            f"timelines undo: failed to project before state: {exc}",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug},
        ) from exc

    try:
        after_projection = replay_projection(backend, stop_at_event_id=target_event.event_id)
    except Exception as exc:
        raise AstridError(
            f"timelines undo: failed to project after state: {exc}",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "event_id": target_event.event_id},
        ) from exc

    # Plan inverses for the target event
    inverses = plan_inverses([target_event], before_projection, after_projection)

    if not inverses:
        print("timelines undo: no inverse planned for target event")
        return 0

    actor = _timeline_actor_from_session(session)
    appended_ids: list[str] = []

    for inv in inverses:
        if inv.invertible and inv.inverse_kind and inv.inverse_payload is not None:
            # Append the mechanical inverse event
            event = backend.append_event(
                target.timeline_id,
                inv.inverse_kind,
                inv.inverse_payload,
                actor=actor,
            )
            appended_ids.append(event.event_id)
        else:
            # Non-invertible: append timeline.reverted
            from astrid.core.timeline.events.schema import TimelineRevertedPayload
            revert_payload = TimelineRevertedPayload(
                target_event_id=target_event.event_id,
                reason=inv.revert_reason or f"undo of {target_event.kind}",
                before_projection=inv.before_projection,
                after_projection=inv.after_projection,
            ).to_json_obj()
            event = backend.append_event(
                target.timeline_id,
                "timeline.reverted",
                revert_payload,
                actor=actor,
            )
            appended_ids.append(event.event_id)

    # Regenerate projection
    try:
        regenerate_projection(
            target.timeline_id,
            backend,
            timeline_home=target.timeline_home,
        )
    except Exception as exc:
        print(f"timelines undo: warning — projection regeneration failed: {exc}")

    print(f"Undo: target event {target_event.event_id} (kind={target_event.kind})")
    print(f"  appended inverse events: {', '.join(appended_ids)}")
    return 0


# ---------------------------------------------------------------------------
# Handler: mass-undo (m9)
# ---------------------------------------------------------------------------


def cmd_mass_undo(args: argparse.Namespace) -> int:
    """Mass-undo events matching filter criteria (preview-first, chunked writes)."""
    session = _require_session()
    project_slug = session.project

    from .observability import resolve_timeline_target
    from .undo import (
        MassUndoSelector,
        execute_mass_undo,
        plan_mass_undo,
    )

    # Validate: at least one filter criterion
    if not (args.ts_since or args.actor_id or args.actor_id_prefix):
        raise AstridError(
            "timelines mass-undo: at least one of --since, --actor, or --actor-prefix must be specified",
            valid_options=["--since", "--actor", "--actor-prefix"],
            recovery_command=f"astrid timelines mass-undo {args.slug} --since <timestamp>",
        )

    # Resolve the timeline
    try:
        target = resolve_timeline_target(project_slug, args.slug)
    except ValueError as exc:
        raise AstridError(
            f"timelines mass-undo: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        ) from exc

    preferred_backend = getattr(args, "from_backend", None) or target.backend

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=preferred_backend,
    )

    # Build selector
    selector = MassUndoSelector(
        ts_since=args.ts_since,
        actor_id=args.actor_id,
        actor_id_prefix=args.actor_id_prefix,
    )

    # Verify chain before any work
    verification = backend.verify_chain()
    if not verification.ok:
        raise AstridError(
            f"timelines mass-undo: chain verification failed: "
            f"{verification.error or 'unknown error'}; refusing to undo",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "verification_error": verification.error},
        )

    actor = _timeline_actor_from_session(session)

    if not args.yes:
        # --- Preview mode ---
        try:
            preview = plan_mass_undo(backend, selector)
        except ValueError as exc:
            raise AstridError(
                f"timelines mass-undo: {exc}",
                recovery_command=f"astrid timelines mass-undo {args.slug} --since <timestamp>",
                state_snapshot={"timeline": args.slug},
            ) from exc

        if preview.matched_count == 0:
            print("mass-undo: no matching events found (preview)")
            return 0

        print(f"mass-undo PREVIEW ({preview.matched_count} candidate(s) of {preview.total_events} total events):")
        print()
        for cand in preview.candidates:
            invertible_str = "MECHANICAL" if cand["invertible"] else "FALLBACK"
            print(f"  {cand['event_id']}  kind={cand['kind']}  →  {invertible_str}")
            if cand["invertible"]:
                print(f"    inverse: {cand['inverse_kind']}  payload={cand['inverse_payload']}")
            else:
                print(f"    reason: {cand['revert_reason']}")
        print()
        print("(Preview only — no writes performed.  Use --yes to execute.)")
        return 0

    # --- Execute mode (--yes) ---
    print("mass-undo: executing with --yes ...")
    try:
        result = execute_mass_undo(
            backend,
            selector,
            timeline_id=target.timeline_id,
            actor=actor,
            timeline_home=target.timeline_home,
        )
    except ValueError as exc:
        raise AstridError(
            f"timelines mass-undo: {exc}",
            recovery_command=f"astrid timelines mass-undo {args.slug} --since <timestamp>",
            state_snapshot={"timeline": args.slug},
        ) from exc

    print("mass-undo result:")
    print(f"  planned: {result.planned_count} inverses")
    print(f"  appended: {result.appended_count} events")
    print(f"  chunks: {result.chunk_count}")
    print(f"  projection regenerated: {result.projection_regenerated}")
    if result.appended_event_ids:
        print(f"  appended IDs: {', '.join(result.appended_event_ids)}")
    if not result.complete:
        raise AstridError(
            f"timelines mass-undo: partial failure: {result.error}",
            recovery_command=f"astrid timelines audit {args.slug}",
            state_snapshot={"timeline": args.slug, "error": result.error},
        )
    if result.error:
        print(f"  warning: {result.error}")

    return 0


# ---------------------------------------------------------------------------
# Handler: erase (m9)
# ---------------------------------------------------------------------------


def cmd_erase(args: argparse.Namespace) -> int:
    """Erase (redact) event payloads matching a selector."""
    session = _require_session()
    project_slug = session.project

    from .erasure import (
        ErasureSelector,
        apply_erasure,
        query_erasure,
    )
    from .observability import resolve_timeline_target

    # Resolve the timeline
    try:
        target = resolve_timeline_target(project_slug, args.slug)
    except ValueError as exc:
        raise AstridError(
            f"timelines erase: {exc}",
            recovery_command="astrid timelines ls",
            state_snapshot={"timeline": args.slug},
        ) from exc

    stream_ref, backend = select_timeline_backend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
        preferred_backend=target.backend,
    )

    # Parse selector
    event_ids = None
    if args.event_ids_raw:
        event_ids = tuple(eid.strip() for eid in args.event_ids_raw.split(",") if eid.strip())

    kind_allowlist = None
    if args.kind_allowlist_raw:
        kind_allowlist = tuple(k.strip() for k in args.kind_allowlist_raw.split(",") if k.strip())

    selector = ErasureSelector(
        event_ids=event_ids,
        kind_allowlist=kind_allowlist,
        actor_id=args.actor_id,
        actor_id_prefix=args.actor_id_prefix,
        ts_after=args.ts_after,
        ts_before=args.ts_before,
    )

    # Always preview first
    try:
        preview = query_erasure(backend, selector)
    except ValueError as exc:
        raise AstridError(
            f"timelines erase: {exc}",
            recovery_command=f"astrid timelines erase {args.slug}",
            state_snapshot={"timeline": args.slug},
        ) from exc

    print(f"Erasure preview for timeline '{args.slug}':")
    print(f"  matched events: {preview.matched_count} of {preview.total_events_in_stream}")
    print(f"  selector: {json.dumps(preview.selector_summary, default=str)}")

    if preview.matched_count == 0:
        print("  (no events match — nothing to erase)")
        return 0

    if not args.yes:
        print()
        if preview.matched_count <= 20:
            print("  Matched event IDs:")
            for eid in preview.matched_event_ids:
                print(f"    - {eid}")
        else:
            print(f"  (showing first 20 of {preview.matched_count} matched event IDs)")
            for eid in preview.matched_event_ids[:20]:
                print(f"    - {eid}")
        print()
        print("  Re-run with --yes to perform the erasure.")
        return 0

    # --yes: perform erasure
    try:
        result = apply_erasure(
            backend,
            selector,
            timeline_id=target.timeline_id,
            actor=_timeline_actor_from_session(session),
            reason=args.reason,
            policy_ref=args.policy_ref,
            timeline_home=target.timeline_home,
        )
    except (ValueError, ProjectionError) as exc:
        raise AstridError(
            f"timelines erase: {exc}",
            recovery_command=f"astrid timelines erase {args.slug}",
            state_snapshot={"timeline": args.slug},
        ) from exc

    print("Erasure applied:")
    print(f"  audit event: {result.audit_event_id}")
    print(f"  payloads replaced: {result.replaced_count}")
    print(f"  downstream recomputed: {result.downstream_count}")
    print(f"  reason: {result.reason}")
    if result.policy_ref:
        print(f"  policy ref: {result.policy_ref}")
    print(f"  projection regenerated: {result.projection_regenerated}")
    print(f"  erased event IDs: {', '.join(result.erased_event_ids)}")
    return 0


# ---------------------------------------------------------------------------
# Handler: recover (m9)
# ---------------------------------------------------------------------------


def cmd_recover(args: argparse.Namespace) -> int:
    """Recover a timeline to a known-good anchor event."""
    session = _require_session()
    project_slug = session.project

    from .operations import recover_to_event

    try:
        result = recover_to_event(
            project_slug,
            args.slug,
            event_id=args.at_event_id,
            actor=_timeline_actor_from_session(session),
            reason=args.reason,
        )
    except (ValueError, ProjectionError) as exc:
        raise AstridError(
            f"timelines recover: {exc}",
            recovery_command=f"astrid timelines recover {args.slug} --at <event-id> --reason <reason>",
            state_snapshot={"timeline": args.slug, "event_id": args.at_event_id},
        ) from exc

    print("Recovery applied:")
    print(f"  anchor event: {result.anchor_event_id} (type={result.anchor_type})")
    print(f"  recovered event: {result.new_event_id}")
    print(f"  new version: {result.new_version}")
    print(f"  reason: {result.reason}")
    print(f"  projection summary: clips={result.projected_head_summary.get('clip_count', 0)}, "
          f"tracks={result.projected_head_summary.get('track_count', 0)}")
    print(f"  regenerated artifacts: {', '.join(result.regenerated_artifact_paths)}")
    return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_optional_session(args: argparse.Namespace) -> Any:
    """Resolve a session if possible, but don't raise when not found.

    Used by commands that accept --project as an alternative to session binding.
    """
    try:
        return resolve_current_session(slug=getattr(args, "project", None) or None)
    except Exception:
        return None


def _resolve_project_slug(args: argparse.Namespace, session: Any) -> str:
    """Resolve a project slug from args or session."""
    project_slug = getattr(args, "project", None)
    if project_slug:
        return project_slug
    if session is not None:
        return session.project
    raise AstridError(
        "no project specified; use --project <slug> or bind a session with 'astrid attach'",
        recovery_command="astrid attach <project>",
    )


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
