"""Parser construction for the timeline CLI.

Extracted from ``astrid/core/timeline/cli.py`` during M4 giant-file split.
``build_parser`` remains the public entry point; it lazily imports command
handlers from ``.cli`` to avoid a circular import between the two modules.
"""

from __future__ import annotations

import argparse

from astrid.core.cli_choices import (
    RecoverableArgumentParser,
    add_choice_arg,
    add_kind_arg,
)

from .kinds import default_transition_kind


def _add_project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        help="Project slug (required when no session is bound).",
    )


def _add_expected_version_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--expected-version",
        type=int,
        dest="expected_version",
        default=None,
        help="Require the current eventlog version to match before applying the mutation.",
    )


def build_parser() -> argparse.ArgumentParser:
    # M4 T12 documented compatibility case: all command handlers are imported
    # through the .cli facade rather than from their canonical modules
    # (cli_crud, cli_output, cli_edits, cli_events, cli_backends) so that
    # legacy monkeypatch seams on ``astrid.core.timeline.cli.cmd_*`` remain
    # interceptable.  The facade module re-exports the canonical definitions.
    # Without this indirection, ``monkeypatch.setattr(timeline_cli, "cmd_ls",
    # fake)`` would not affect the handler references stored by the parser,
    # breaking ~50+ existing tests and any runtime monkeypatching tools.
    #
    # Canonical modules per handler domain:
    #   cli_crud    — lifecycle (ls, create, show, rename, finalize, tombstone,
    #                 purge, set-default)
    #   cli_output  — export, cost
    #   cli_edits   — clip, transition, effect, theme, track, audio, pool,
    #                 arrangement
    #   cli_events  — history, diff, audit, preview, who-edited, migrate-events
    #   cli_backends — push, pull, branch, undo, mass-undo, erase, recover
    from .cli import (  # noqa: PLC0415
        # -- cli_crud --
        cmd_create,
        cmd_finalize,
        cmd_ls,
        cmd_purge,
        cmd_rename,
        cmd_set_default,
        cmd_show,
        cmd_tombstone,
        # -- cli_output --
        cmd_cost,
        cmd_export,
        # -- cli_edits --
        cmd_arrangement_set,
        cmd_arrangement_show,
        cmd_audio_bind,
        cmd_audio_unbind,
        cmd_clip_add,
        cmd_clip_annotate,
        cmd_clip_move,
        cmd_clip_remove,
        cmd_clip_replace,
        cmd_clip_retime,
        cmd_clip_retrack,
        cmd_clip_set_text,
        cmd_clip_swap,
        cmd_effect_add,
        cmd_effect_remove,
        cmd_effect_tune,
        cmd_pool_add,
        cmd_pool_remove,
        cmd_pool_score,
        cmd_theme_override,
        cmd_theme_set,
        cmd_track_add,
        cmd_track_remove,
        cmd_transition_remove,
        cmd_transition_set,
        # -- cli_events --
        cmd_audit,
        cmd_diff,
        cmd_history,
        cmd_migrate_events,
        cmd_preview,
        cmd_who_edited,
        # -- cli_backends --
        cmd_branch_create,
        cmd_branch_list,
        cmd_erase,
        cmd_mass_undo,
        cmd_pull,
        cmd_push,
        cmd_recover,
        cmd_undo,
    )

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
    _add_project_arg(create_parser)
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
    _add_project_arg(show_parser)
    show_parser.set_defaults(handler=cmd_show)

    # --- rename ---
    rename_parser = subparsers.add_parser("rename", help="Rename a timeline slug.")
    rename_parser.add_argument("old_slug", metavar="slug", help="Current timeline slug.")
    rename_parser.add_argument("new_slug", metavar="new-slug", help="New timeline slug.")
    _add_expected_version_arg(rename_parser)
    _add_project_arg(rename_parser)
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
    _add_project_arg(finalize_parser)
    finalize_parser.set_defaults(handler=cmd_finalize)

    # --- tombstone ---
    tombstone_parser = subparsers.add_parser(
        "tombstone", help="Soft-delete a timeline (marks tombstoned, leaves files)."
    )
    tombstone_parser.add_argument("slug", help="Timeline slug.")
    _add_project_arg(tombstone_parser)
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
    _add_project_arg(purge_parser)
    purge_parser.set_defaults(handler=cmd_purge)

    # --- set-default ---
    set_default_parser = subparsers.add_parser(
        "set-default", help="Set a timeline as the project default."
    )
    set_default_parser.add_argument("slug", help="Timeline slug.")
    _add_project_arg(set_default_parser)
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
    _add_project_arg(export_parser)
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
    _add_project_arg(cost_parser)
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
    _add_project_arg(history_parser)
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
    _add_project_arg(diff_parser)
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
    _add_project_arg(audit_parser)
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
    _add_project_arg(preview_parser)
    preview_parser.set_defaults(handler=cmd_preview)

    # --- who-edited (m7) ---
    who_edited_parser = subparsers.add_parser(
        "who-edited", help="Show actor rollup for a timeline."
    )
    who_edited_parser.add_argument(
        "slug_or_id", help="Timeline slug, ULID, or event-stream UUID."
    )
    _add_project_arg(who_edited_parser)
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
    _add_project_arg(clip_add)
    clip_add.set_defaults(handler=cmd_clip_add)

    # clip remove
    clip_remove = clip_subs.add_parser("remove", help="Remove a clip from a timeline.")
    clip_remove.add_argument("slug", help="Timeline slug.")
    clip_remove.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    _add_expected_version_arg(clip_remove)
    _add_project_arg(clip_remove)
    clip_remove.set_defaults(handler=cmd_clip_remove)

    # clip move
    clip_move = clip_subs.add_parser("move", help="Move a clip to a new position.")
    clip_move.add_argument("slug", help="Timeline slug.")
    clip_move.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_move.add_argument("--to", required=True, dest="to_position", help="Target position: index, after:<id>, or before:<id>.")
    _add_expected_version_arg(clip_move)
    _add_project_arg(clip_move)
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
    _add_project_arg(clip_retrack)
    clip_retrack.set_defaults(handler=cmd_clip_retrack)

    # clip retime
    clip_retime = clip_subs.add_parser("retime", help="Change a clip's start time and duration.")
    clip_retime.add_argument("slug", help="Timeline slug.")
    clip_retime.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_retime.add_argument("--start", required=True, type=float, help="Start time in seconds (>= 0).")
    clip_retime.add_argument("--duration", required=True, type=float, help="Duration in seconds (> 0).")
    _add_expected_version_arg(clip_retime)
    _add_project_arg(clip_retime)
    clip_retime.set_defaults(handler=cmd_clip_retime)

    # clip swap
    clip_swap = clip_subs.add_parser("swap", help="Swap the positions of two clips.")
    clip_swap.add_argument("slug", help="Timeline slug.")
    clip_swap.add_argument("--a", required=True, dest="clip_a", help="First clip identifier.")
    clip_swap.add_argument("--b", required=True, dest="clip_b", help="Second clip identifier.")
    _add_expected_version_arg(clip_swap)
    _add_project_arg(clip_swap)
    clip_swap.set_defaults(handler=cmd_clip_swap)

    # clip replace
    clip_replace = clip_subs.add_parser("replace", help="Replace a clip with a different asset.")
    clip_replace.add_argument("slug", help="Timeline slug.")
    clip_replace.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_replace.add_argument("--with", required=True, dest="with_asset_id", metavar="ASSET_ID", help="Replacement asset identifier.")
    _add_expected_version_arg(clip_replace)
    _add_project_arg(clip_replace)
    clip_replace.set_defaults(handler=cmd_clip_replace)

    # clip set-text
    clip_set_text = clip_subs.add_parser("set-text", help="Set the text content of a text clip.")
    clip_set_text.add_argument("slug", help="Timeline slug.")
    clip_set_text.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_set_text.add_argument("--text", required=True, help="Text content.")
    _add_expected_version_arg(clip_set_text)
    _add_project_arg(clip_set_text)
    clip_set_text.set_defaults(handler=cmd_clip_set_text)

    # clip annotate
    clip_annotate = clip_subs.add_parser("annotate", help="Add a note annotation to a clip.")
    clip_annotate.add_argument("slug", help="Timeline slug.")
    clip_annotate.add_argument("--clip-id", required=True, dest="clip_id", help="Clip identifier.")
    clip_annotate.add_argument("--note", required=True, help="Annotation note text.")
    _add_expected_version_arg(clip_annotate)
    _add_project_arg(clip_annotate)
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
    _add_project_arg(trans_set)
    trans_set.set_defaults(handler=cmd_transition_set)

    # transition remove
    trans_remove = trans_subs.add_parser("remove", help="Remove a transition between two clips.")
    trans_remove.add_argument("slug", help="Timeline slug.")
    trans_remove.add_argument("--between", required=True, metavar="LEFT,RIGHT",
                              help="Two clip ids separated by comma (left clip, right clip).")
    _add_expected_version_arg(trans_remove)
    _add_project_arg(trans_remove)
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
    _add_project_arg(effect_add_p)
    effect_add_p.set_defaults(handler=cmd_effect_add)

    # effect remove
    effect_remove_p = effect_subs.add_parser("remove", help="Remove an effect from a clip.")
    effect_remove_p.add_argument("slug", help="Timeline slug.")
    effect_remove_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    effect_remove_p.add_argument("--effect-id", required=True, dest="effect_id", help="Effect identifier.")
    _add_expected_version_arg(effect_remove_p)
    _add_project_arg(effect_remove_p)
    effect_remove_p.set_defaults(handler=cmd_effect_remove)

    # effect tune
    effect_tune_p = effect_subs.add_parser("tune", help="Tune an effect parameter.")
    effect_tune_p.add_argument("slug", help="Timeline slug.")
    effect_tune_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    effect_tune_p.add_argument("--effect-id", required=True, dest="effect_id", help="Effect identifier.")
    effect_tune_p.add_argument("--param", required=True, help="Parameter name (k).")
    effect_tune_p.add_argument("--value", required=True, help="Parameter value (parsed as JSON).")
    _add_expected_version_arg(effect_tune_p)
    _add_project_arg(effect_tune_p)
    effect_tune_p.set_defaults(handler=cmd_effect_tune)

    # --- theme ---
    theme_parser = subparsers.add_parser("theme", help="Manage timeline theme.")
    theme_subs = theme_parser.add_subparsers(dest="theme_command", required=True)

    # theme set
    theme_set_p = theme_subs.add_parser("set", help="Set the active theme.")
    theme_set_p.add_argument("slug", help="Timeline slug.")
    theme_set_p.add_argument("--theme", required=True, dest="theme_id", help="Theme identifier.")
    _add_expected_version_arg(theme_set_p)
    _add_project_arg(theme_set_p)
    theme_set_p.set_defaults(handler=cmd_theme_set)

    # theme override
    theme_override_p = theme_subs.add_parser("override", help="Override a theme namespace value.")
    theme_override_p.add_argument("slug", help="Timeline slug.")
    theme_override_p.add_argument("--override-id", required=True, dest="override_id",
                                  help="Override namespace (visual|generation|voice|audio|pacing).")
    theme_override_p.add_argument("--value", required=True, help="Override value (parsed as JSON).")
    _add_expected_version_arg(theme_override_p)
    _add_project_arg(theme_override_p)
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
    _add_project_arg(track_add_p)
    track_add_p.set_defaults(handler=cmd_track_add)

    # track remove
    track_remove_p = track_subs.add_parser("remove", help="Remove a track.")
    track_remove_p.add_argument("slug", help="Timeline slug.")
    track_remove_p.add_argument("--track-id", required=True, dest="track_id", help="Track identifier.")
    _add_expected_version_arg(track_remove_p)
    _add_project_arg(track_remove_p)
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
    _add_project_arg(audio_bind_p)
    audio_bind_p.set_defaults(handler=cmd_audio_bind)

    # audio unbind
    audio_unbind_p = audio_subs.add_parser("unbind", help="Unbind audio from a clip.")
    audio_unbind_p.add_argument("slug", help="Timeline slug.")
    audio_unbind_p.add_argument("--clip", required=True, dest="clip_id", help="Clip identifier.")
    _add_expected_version_arg(audio_unbind_p)
    _add_project_arg(audio_unbind_p)
    audio_unbind_p.set_defaults(handler=cmd_audio_unbind)

    # --- pool ---
    pool_parser = subparsers.add_parser("pool", help="Manage asset pool.")
    pool_subs = pool_parser.add_subparsers(dest="pool_command", required=True)

    # pool add
    pool_add_p = pool_subs.add_parser("add", help="Add an asset to the pool.")
    pool_add_p.add_argument("slug", help="Timeline slug.")
    pool_add_p.add_argument("--asset", required=True, dest="asset_id", help="Asset identifier.")
    _add_expected_version_arg(pool_add_p)
    _add_project_arg(pool_add_p)
    pool_add_p.set_defaults(handler=cmd_pool_add)

    # pool remove
    pool_remove_p = pool_subs.add_parser("remove", help="Remove an asset from the pool.")
    pool_remove_p.add_argument("slug", help="Timeline slug.")
    pool_remove_p.add_argument("--asset-id", required=True, dest="asset_id", help="Asset identifier.")
    _add_expected_version_arg(pool_remove_p)
    _add_project_arg(pool_remove_p)
    pool_remove_p.set_defaults(handler=cmd_pool_remove)

    # pool score
    pool_score_p = pool_subs.add_parser("score", help="Score a pool asset.")
    pool_score_p.add_argument("slug", help="Timeline slug.")
    pool_score_p.add_argument("--asset-id", required=True, dest="asset_id", help="Asset identifier.")
    pool_score_p.add_argument("--score", type=float, required=True, help="Score between 0 and 1.")
    _add_expected_version_arg(pool_score_p)
    _add_project_arg(pool_score_p)
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
    _add_project_arg(arr_set_p)
    arr_set_p.set_defaults(handler=cmd_arrangement_set)

    # arrangement show
    arr_show_p = arr_subs.add_parser("show", help="Show the current arrangement.")
    arr_show_p.add_argument("slug", help="Timeline slug.")
    arr_show_p.add_argument("--json", dest="json_out", action="store_true",
                            help="Emit structured JSON.")
    _add_project_arg(arr_show_p)
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
    _add_project_arg(branch_create)
    branch_create.set_defaults(handler=cmd_branch_create)

    # branch list
    branch_list = branch_subs.add_parser(
        "list", help="List branches of a source timeline."
    )
    branch_list.add_argument(
        "source_slug_or_id", help="Source timeline slug, ULID, or UUID."
    )
    _add_project_arg(branch_list)
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
    _add_project_arg(erase_parser)
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
    _add_project_arg(branches_parser)
    branches_parser.set_defaults(handler=cmd_branch_list)

    return parser
