"""Parser construction for the timeline CLI.

Extracted from ``astrid/core/timeline/cli.py`` during M4 giant-file split.
``build_parser`` remains the public entry point; it lazily imports command
handlers from ``.cli`` to avoid a circular import between the two modules.

P5-4: The 829-line repetitive ``build_parser()`` body was replaced with a
declarative ``_COMMANDS`` table (~200 lines) + generic ``_build_parser_from_table()``
iterator (~50 lines).  The resulting parser is byte-identical in argparse
behaviour (same subcommands, args, defaults, help).
"""

from __future__ import annotations

import argparse
from typing import Any, Callable

from astrid.core.cli.choices_registry import add_kind_arg
from astrid.core.cli_choices import (
    RecoverableArgumentParser,
    add_choice_arg,
)
from astrid.core.timeline.kinds import default_transition_kind

# ── Shared helpers (kept public — cli.py delegates to these) ────────────────


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


# ── Declarative command table ───────────────────────────────────────────────
#
# Each entry is a dict with:
#   name         – subcommand name
#   help         – help string
#   handler      – attribute name on the .cli facade module (resolved at call time)
#   aliases?     – list of alias strings
#   dest?        – dest for nested subparsers (defaults to <name>_command)
#   args?        – list of ArgSpec dicts (see _apply_arg_spec)
#   subcommands? – list of nested CommandSpec dicts
#
# ArgSpec forms (checked in this order):
#   {"project_arg": True}                          → _add_project_arg(parser)
#   {"expected_version_arg": True}                 → _add_expected_version_arg(parser)
#   {"kind_arg": {"flags": [...], "catalog": "...", ...}}
#   {"choice_arg": {"flags": [...], "values": (...), ...}}
#   {"mutex_group": [ArgSpec...], "mutex_required"?: bool}
#   {"name": "<positional>", "help": "...", "metavar"?: "..."}
#   {"flags": ["--flag"], ...}                     → parser.add_argument(*flags, ...)


_COMMANDS: list[dict[str, Any]] = [
    # ── ls ──
    {
        "name": "ls",
        "aliases": ["list"],
        "help": "List timelines in the current project.",
        "handler": "cmd_ls",
        "args": [
            {"project_arg": True},
            {
                "flags": ["--include-tombstoned"],
                "action": "store_true",
                "help": "Include tombstoned timelines for audit views.",
            },
        ],
    },
    # ── create ──
    {
        "name": "create",
        "help": "Create a timeline.",
        "handler": "cmd_create",
        "args": [
            {
                "name": "slug",
                "help": "Timeline slug (lowercase, letters/digits/hyphens).",
            },
            {"flags": ["--name"], "help": "Human-readable name (defaults to slug)."},
            {
                "flags": ["--default"],
                "action": "store_true",
                "dest": "is_default",
                "help": "Set as the project default timeline.",
            },
            {"project_arg": True},
        ],
    },
    # ── show ──
    {
        "name": "show",
        "help": "Show a timeline.",
        "handler": "cmd_show",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "flags": ["--verify"],
                "action": "store_true",
                "help": "Recompute integrity (sha256) for each final output.",
            },
            {
                "flags": ["--json"],
                "dest": "json_out",
                "action": "store_true",
                "help": "Emit structured JSON instead of pretty-print.",
            },
            {"project_arg": True},
        ],
    },
    # ── rename ──
    {
        "name": "rename",
        "help": "Rename a timeline slug.",
        "handler": "cmd_rename",
        "args": [
            {"name": "old_slug", "metavar": "slug", "help": "Current timeline slug."},
            {"name": "new_slug", "metavar": "new-slug", "help": "New timeline slug."},
            {"expected_version_arg": True},
            {"project_arg": True},
        ],
    },
    # ── finalize ──
    {
        "name": "finalize",
        "help": "Record a final output with sha256 integrity.",
        "handler": "cmd_finalize",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {"flags": ["--output"], "required": True, "help": "Path to the output file."},
            {
                "flags": ["--kind"],
                "default": "unknown",
                "help": "Free-text output kind (mp4, transcript, etc.).",
            },
            {
                "flags": ["--from-run"],
                "help": "Run ID this output originates from (defaults to the current run).",
            },
            {
                "flags": ["--recorded-by"],
                "default": "agent:cli",
                "help": "Agent identifier.",
            },
            {"project_arg": True},
        ],
    },
    # ── tombstone ──
    {
        "name": "tombstone",
        "help": "Soft-delete a timeline (marks tombstoned, leaves files).",
        "handler": "cmd_tombstone",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {"project_arg": True},
        ],
    },
    # ── purge ──
    {
        "name": "purge",
        "help": "Hard-delete a timeline directory tree.",
        "handler": "cmd_purge",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "flags": ["--yes-really"],
                "action": "store_true",
                "help": "Confirm you really want to delete this timeline permanently.",
            },
            {"project_arg": True},
        ],
    },
    # ── set-default ──
    {
        "name": "set-default",
        "help": "Set a timeline as the project default.",
        "handler": "cmd_set_default",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {"project_arg": True},
        ],
    },
    # ── export ──
    {
        "name": "export",
        "help": "Export a timeline bundle.",
        "handler": "cmd_export",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "flags": ["--out"],
                "required": True,
                "help": "Output tarball path (.tar.gz).",
            },
            {
                "flags": ["--include-aborted"],
                "action": "store_true",
                "help": "Include aborted runs in the export bundle.",
            },
            {"project_arg": True},
        ],
    },
    # ── cost ──
    {
        "name": "cost",
        "help": "Show cost rollup for a timeline.",
        "handler": "cmd_cost",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "flags": ["--json"],
                "dest": "json_out",
                "action": "store_true",
                "help": "Emit structured JSON instead of pretty-print.",
            },
            {
                "flags": ["--include-aborted"],
                "action": "store_true",
                "help": "Include aborted runs in the cost rollup.",
            },
            {"project_arg": True},
        ],
    },
    # ── history ──
    {
        "name": "history",
        "help": "Read the event history of a timeline.",
        "handler": "cmd_history",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Timeline slug, ULID, or event-stream UUID.",
            },
            {
                "flags": ["--since"],
                "dest": "since_event_id",
                "default": None,
                "help": "Start reading after this event ID.",
            },
            {
                "flags": ["--limit"],
                "type": int,
                "default": 50,
                "help": "Maximum number of events to return (default: 50).",
            },
            {"project_arg": True},
        ],
    },
    # ── diff ──
    {
        "name": "diff",
        "help": "Semantic diff between two events.",
        "handler": "cmd_diff",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Timeline slug, ULID, or event-stream UUID.",
            },
            {
                "flags": ["--from"],
                "required": True,
                "dest": "from_event_id",
                "help": "Starting event ID for the diff.",
            },
            {
                "flags": ["--to"],
                "required": True,
                "dest": "to_event_id",
                "help": "Ending event ID for the diff.",
            },
            {
                "flags": ["--with-state"],
                "action": "store_true",
                "help": "Include projected before/after assembly snapshots.",
            },
            {"project_arg": True},
        ],
    },
    # ── audit ──
    {
        "name": "audit",
        "help": "Verify event chain integrity and projection parity.",
        "handler": "cmd_audit",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Timeline slug, ULID, or event-stream UUID.",
            },
            {
                "flags": ["--include-ops"],
                "action": "store_true",
                "dest": "include_ops",
                "help": "Include operational failure logs in the audit report.",
            },
            {"project_arg": True},
        ],
    },
    # ── preview ──
    {
        "name": "preview",
        "help": "Project a past state at a specific event.",
        "handler": "cmd_preview",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Timeline slug, ULID, or event-stream UUID.",
            },
            {
                "flags": ["--at"],
                "required": True,
                "dest": "at_event_id",
                "help": "Event ID to project state at.",
            },
            {
                "flags": ["--out"],
                "dest": "out_path",
                "default": None,
                "help": "Write projected state to this file (default: stdout).",
            },
            {"project_arg": True},
        ],
    },
    # ── who-edited ──
    {
        "name": "who-edited",
        "help": "Show actor rollup for a timeline.",
        "handler": "cmd_who_edited",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Timeline slug, ULID, or event-stream UUID.",
            },
            {"project_arg": True},
        ],
    },
    # ── registry (group) ──
    {
        "name": "registry",
        "help": "Manage the timeline asset registry.",
        "dest": "registry_command",
        "handler": "",  # group node — handler set on leaf subcommands
        "subcommands": [
            # registry sync
            {
                "name": "sync",
                "help": "Sync asset registry entries from a JSON manifest.",
                "handler": "cmd_registry_sync",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--manifest"],
                        "required": True,
                        "help": "Path to the JSON manifest file.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── clip (group) ──
    {
        "name": "clip",
        "help": "Edit clips in a timeline.",
        "dest": "clip_command",
        "handler": "",  # group node — handler set on leaf subcommands
        "subcommands": [
            # clip add
            {
                "name": "add",
                "help": "Add a clip to a timeline.",
                "handler": "cmd_clip_add",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "kind_arg": {
                            "flags": ["--kind"],
                            "catalog": "clip",
                            "required": True,
                            "help": "Clip kind.",
                        }
                    },
                    {
                        "flags": ["--asset"],
                        "required": True,
                        "help": "Asset identifier.",
                    },
                    {
                        "flags": ["--track", "--track-id"],
                        "required": True,
                        "dest": "track_id",
                        "help": "Existing target track identifier for the clip.",
                    },
                    {
                        "mutex_group": [
                            {
                                "flags": ["--at"],
                                "type": int,
                                "dest": "at_index",
                                "help": "Insert at 0-based index.",
                            },
                            {
                                "flags": ["--after"],
                                "dest": "after_id",
                                "help": "Insert after clip id.",
                            },
                            {
                                "flags": ["--before"],
                                "dest": "before_id",
                                "help": "Insert before clip id.",
                            },
                        ],
                    },
                    {
                        "flags": ["--start"],
                        "type": float,
                        "default": 0.0,
                        "help": "Start time in seconds (>= 0, default: 0.0).",
                    },
                    {
                        "flags": ["--duration"],
                        "type": float,
                        "default": None,
                        "help": "Duration in seconds (> 0). For audio clips without a registry entry this is required.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip remove
            {
                "name": "remove",
                "help": "Remove a clip from a timeline.",
                "handler": "cmd_clip_remove",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip-id"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip move
            {
                "name": "move",
                "help": "Move a clip to a new position.",
                "handler": "cmd_clip_move",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip-id"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--to"],
                        "required": True,
                        "dest": "to_position",
                        "help": "Target position: index, after:<id>, or before:<id>.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip retrack
            {
                "name": "retrack",
                "help": "Move a clip to a different track.",
                "handler": "cmd_clip_retrack",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip-id"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--track", "--track-id"],
                        "required": True,
                        "dest": "track_id",
                        "help": "Existing target track identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip retime
            {
                "name": "retime",
                "help": "Change a clip's start time and duration.",
                "handler": "cmd_clip_retime",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip-id"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--start"],
                        "required": True,
                        "type": float,
                        "help": "Start time in seconds (>= 0).",
                    },
                    {
                        "flags": ["--duration"],
                        "required": True,
                        "type": float,
                        "help": "Duration in seconds (> 0).",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip swap
            {
                "name": "swap",
                "help": "Swap the positions of two clips.",
                "handler": "cmd_clip_swap",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--a"],
                        "required": True,
                        "dest": "clip_a",
                        "help": "First clip identifier.",
                    },
                    {
                        "flags": ["--b"],
                        "required": True,
                        "dest": "clip_b",
                        "help": "Second clip identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip replace
            {
                "name": "replace",
                "help": "Replace a clip with a different asset.",
                "handler": "cmd_clip_replace",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip-id"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--with"],
                        "required": True,
                        "dest": "with_asset_id",
                        "metavar": "ASSET_ID",
                        "help": "Replacement asset identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip set-text
            {
                "name": "set-text",
                "help": "Set the text content of a text clip.",
                "handler": "cmd_clip_set_text",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip-id"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {"flags": ["--text"], "required": True, "help": "Text content."},
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # clip annotate
            {
                "name": "annotate",
                "help": "Add a note annotation to a clip.",
                "handler": "cmd_clip_annotate",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip-id"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--note"],
                        "required": True,
                        "help": "Annotation note text.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── transition (group) ──
    {
        "name": "transition",
        "help": "Manage transitions between clips.",
        "dest": "transition_command",
        "handler": "",
        "subcommands": [
            # transition set
            {
                "name": "set",
                "help": "Set a transition between two clips.",
                "handler": "cmd_transition_set",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--between"],
                        "required": True,
                        "metavar": "LEFT,RIGHT",
                        "help": "Two clip ids separated by comma (left clip, right clip).",
                    },
                    {
                        "kind_arg": {
                            "flags": ["--kind"],
                            "catalog": "transition",
                            "default": default_transition_kind(),
                            "help": "Transition kind.",
                        }
                    },
                    {
                        "flags": ["--duration"],
                        "type": float,
                        "default": 0.5,
                        "dest": "duration_seconds",
                        "help": "Transition duration in seconds (default: 0.5).",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # transition remove
            {
                "name": "remove",
                "help": "Remove a transition between two clips.",
                "handler": "cmd_transition_remove",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--between"],
                        "required": True,
                        "metavar": "LEFT,RIGHT",
                        "help": "Two clip ids separated by comma (left clip, right clip).",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── effect (group) ──
    {
        "name": "effect",
        "help": "Manage clip effects.",
        "dest": "effect_command",
        "handler": "",
        "subcommands": [
            # effect add
            {
                "name": "add",
                "help": "Add an effect to a clip.",
                "handler": "cmd_effect_add",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--effect-id"],
                        "required": True,
                        "dest": "effect_id",
                        "help": "Effect identifier.",
                    },
                    {
                        "flags": ["--params"],
                        "action": "append",
                        "dest": "params_raw",
                        "metavar": "k=v",
                        "help": "Effect parameter as k=v (repeatable).",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # effect remove
            {
                "name": "remove",
                "help": "Remove an effect from a clip.",
                "handler": "cmd_effect_remove",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--effect-id"],
                        "required": True,
                        "dest": "effect_id",
                        "help": "Effect identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # effect tune
            {
                "name": "tune",
                "help": "Tune an effect parameter.",
                "handler": "cmd_effect_tune",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--effect-id"],
                        "required": True,
                        "dest": "effect_id",
                        "help": "Effect identifier.",
                    },
                    {
                        "flags": ["--param"],
                        "required": True,
                        "help": "Parameter name (k).",
                    },
                    {
                        "flags": ["--value"],
                        "required": True,
                        "help": "Parameter value (parsed as JSON).",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── theme (group) ──
    {
        "name": "theme",
        "help": "Manage timeline theme.",
        "dest": "theme_command",
        "handler": "",
        "subcommands": [
            # theme set
            {
                "name": "set",
                "help": "Set the active theme.",
                "handler": "cmd_theme_set",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--theme"],
                        "required": True,
                        "dest": "theme_id",
                        "help": "Theme identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # theme override
            {
                "name": "override",
                "help": "Override a theme namespace value.",
                "handler": "cmd_theme_override",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--override-id"],
                        "required": True,
                        "dest": "override_id",
                        "help": "Override namespace (visual|generation|voice|audio|pacing).",
                    },
                    {
                        "flags": ["--value"],
                        "required": True,
                        "help": "Override value (parsed as JSON).",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── track (group) ──
    {
        "name": "track",
        "help": "Manage timeline tracks.",
        "dest": "track_command",
        "handler": "",
        "subcommands": [
            # track add
            {
                "name": "add",
                "help": "Add a track.",
                "handler": "cmd_track_add",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "kind_arg": {
                            "flags": ["--kind"],
                            "catalog": "track",
                            "required": True,
                            "help": "Track kind.",
                        }
                    },
                    {
                        "flags": ["--label"],
                        "default": None,
                        "help": "Optional human-readable label.",
                    },
                    {
                        "flags": ["--track-id"],
                        "default": None,
                        "dest": "track_id",
                        "help": "Track identifier (auto-generated UUID if omitted).",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # track remove
            {
                "name": "remove",
                "help": "Remove a track.",
                "handler": "cmd_track_remove",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--track-id"],
                        "required": True,
                        "dest": "track_id",
                        "help": "Track identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── audio (group) ──
    {
        "name": "audio",
        "help": "Manage clip audio bindings.",
        "dest": "audio_command",
        "handler": "",
        "subcommands": [
            # audio bind
            {
                "name": "bind",
                "help": "Bind audio asset to a clip.",
                "handler": "cmd_audio_bind",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {
                        "flags": ["--asset"],
                        "required": True,
                        "dest": "asset_id",
                        "help": "Audio asset identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # audio unbind
            {
                "name": "unbind",
                "help": "Unbind audio from a clip.",
                "handler": "cmd_audio_unbind",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--clip"],
                        "required": True,
                        "dest": "clip_id",
                        "help": "Clip identifier.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── arrangement (group) ──
    {
        "name": "arrangement",
        "help": "Manage arrangement.",
        "dest": "arrangement_command",
        "handler": "",
        "subcommands": [
            # arrangement set
            {
                "name": "set",
                "help": "Retired: arrangement replacement is migration-only legacy.",
                "handler": "cmd_arrangement_set",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--from-json"],
                        "required": True,
                        "dest": "from_json",
                        "help": "Path to a JSON file containing the new arrangement.",
                    },
                    {"expected_version_arg": True},
                    {"project_arg": True},
                ],
            },
            # arrangement show
            {
                "name": "show",
                "help": "Show the current arrangement.",
                "handler": "cmd_arrangement_show",
                "args": [
                    {"name": "slug", "help": "Timeline slug."},
                    {
                        "flags": ["--json"],
                        "dest": "json_out",
                        "action": "store_true",
                        "help": "Emit structured JSON.",
                    },
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── migrate-events ──
    {
        "name": "migrate-events",
        "help": "Migrate legacy timeline data into event streams.",
        "handler": "cmd_migrate_events",
        "args": [
            {
                "flags": ["--dry-run"],
                "action": "store_true",
                "default": True,
                "help": "Preview migration without writing (default).",
            },
            {
                "flags": ["--apply"],
                "action": "store_true",
                "dest": "apply",
                "default": False,
                "help": "Actually write event-stream imports.",
            },
            {
                "mutex_group": [
                    {
                        "flags": ["--project"],
                        "dest": "project_slug",
                        "help": "Migrate timelines for one project slug.",
                    },
                    {
                        "flags": ["--all-projects"],
                        "action": "store_true",
                        "dest": "all_projects",
                        "help": "Migrate timelines across all discovered projects.",
                    },
                ],
                "mutex_required": True,
            },
            {
                "flags": ["--json"],
                "dest": "json_out",
                "action": "store_true",
                "help": "Emit structured JSON instead of pretty-print.",
            },
        ],
    },
    # ── push ──
    {
        "name": "push",
        "help": "Push a local timeline to Supabase via event-log replay.",
        "handler": "cmd_push",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Local timeline slug, ULID, or event-stream UUID.",
            },
            {
                "choice_arg": {
                    "flags": ["--to"],
                    "values": ("supabase",),
                    "dest": "to_backend",
                    "required": True,
                    "help": "Destination backend (only 'supabase' in v1).",
                }
            },
            {"project_arg": True},
        ],
    },
    # ── pull ──
    {
        "name": "pull",
        "help": "Pull a Supabase timeline to a local destination via event-log replay.",
        "handler": "cmd_pull",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Remote timeline slug or event-stream UUID on Supabase.",
            },
            {
                "choice_arg": {
                    "flags": ["--from"],
                    "values": ("supabase",),
                    "dest": "from_backend",
                    "required": True,
                    "help": "Source backend (only 'supabase' in v1).",
                }
            },
            {
                "flags": ["--project"],
                "required": True,
                "help": "Project slug for the local destination.",
            },
            {
                "flags": ["--into"],
                "dest": "into_slug",
                "default": None,
                "help": "Pull into an existing local timeline with this slug.",
            },
            {
                "flags": ["--as"],
                "dest": "create_as_slug",
                "default": None,
                "help": "Create a new local timeline with this slug (requires --create).",
            },
            {
                "flags": ["--create"],
                "action": "store_true",
                "default": False,
                "help": "Create a new local timeline as the pull destination.",
            },
        ],
    },
    # ── sync (S5) ──
    {
        "name": "sync",
        "help": "Unified push-then-pull: sync a local timeline with Supabase.",
        "handler": "cmd_sync",
        "args": [
            {
                "name": "slug_or_id",
                "help": "Local timeline slug, ULID, or event-stream UUID.",
            },
            {"project_arg": True},
        ],
    },
    # ── branch (group) ──
    {
        "name": "branch",
        "help": "Manage timeline branches.",
        "dest": "branch_command",
        "handler": "",
        "subcommands": [
            # branch create
            {
                "name": "create",
                "help": "Create a branch from a source timeline at a specific event.",
                "handler": "cmd_branch_create",
                "args": [
                    {
                        "name": "source_slug_or_id",
                        "help": "Source timeline slug, ULID, or UUID.",
                    },
                    {
                        "name": "branch_slug",
                        "help": "Slug for the new branch timeline.",
                    },
                    {
                        "flags": ["--from"],
                        "required": True,
                        "dest": "from_event_id",
                        "help": "Source event ID to branch from (anchor point).",
                    },
                    {
                        "flags": ["--reason"],
                        "default": "",
                        "help": "Human-readable reason for the branch.",
                    },
                    {"project_arg": True},
                ],
            },
            # branch list
            {
                "name": "list",
                "help": "List branches of a source timeline.",
                "handler": "cmd_branch_list",
                "args": [
                    {
                        "name": "source_slug_or_id",
                        "help": "Source timeline slug, ULID, or UUID.",
                    },
                    {"project_arg": True},
                ],
            },
        ],
    },
    # ── undo ──
    {
        "name": "undo",
        "help": "Undo the latest undoable event on a timeline.",
        "handler": "cmd_undo",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "choice_arg": {
                    "flags": ["--from"],
                    "values": ("supabase",),
                    "dest": "from_backend",
                    "default": None,
                    "help": "Backend to undo on (default: local_fs).",
                }
            },
            {"project_arg": True},
        ],
    },
    # ── mass-undo ──
    {
        "name": "mass-undo",
        "help": "Preview-first mass undo of events matching filter criteria.",
        "handler": "cmd_mass_undo",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "flags": ["--since"],
                "dest": "ts_since",
                "default": None,
                "help": "Timestamp ISO-8601 lower bound (inclusive) — only undo events at or after this time.",
            },
            {
                "flags": ["--actor"],
                "dest": "actor_id",
                "default": None,
                "help": "Exact actor ID match.",
            },
            {
                "flags": ["--actor-prefix"],
                "dest": "actor_id_prefix",
                "default": None,
                "help": "Actor ID prefix match.",
            },
            {
                "flags": ["--yes"],
                "action": "store_true",
                "default": False,
                "help": "Confirm mass undo (required to actually write).",
            },
            {
                "choice_arg": {
                    "flags": ["--from"],
                    "values": ("supabase",),
                    "dest": "from_backend",
                    "default": None,
                    "help": "Backend to undo on (default: local_fs).",
                }
            },
            {"project_arg": True},
        ],
    },
    # ── erase ──
    {
        "name": "erase",
        "help": "Erase (redact) event payloads matching a selector.",
        "handler": "cmd_erase",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "flags": ["--event-ids"],
                "dest": "event_ids_raw",
                "default": None,
                "help": "Comma-separated event IDs (ULIDs) to erase.",
            },
            {
                "flags": ["--kind"],
                "dest": "kind_allowlist_raw",
                "default": None,
                "help": "Comma-separated event kind allowlist (e.g. 'clip.added,clip.removed').",
            },
            {
                "flags": ["--actor"],
                "dest": "actor_id",
                "default": None,
                "help": "Exact actor ID match.",
            },
            {
                "flags": ["--actor-prefix"],
                "dest": "actor_id_prefix",
                "default": None,
                "help": "Actor ID prefix match.",
            },
            {
                "flags": ["--after"],
                "dest": "ts_after",
                "default": None,
                "help": "Timestamp ISO-8601 lower bound (inclusive).",
            },
            {
                "flags": ["--before"],
                "dest": "ts_before",
                "default": None,
                "help": "Timestamp ISO-8601 upper bound (inclusive).",
            },
            {
                "flags": ["--reason"],
                "required": True,
                "help": "Human-readable reason for the erasure.",
            },
            {
                "flags": ["--policy-ref"],
                "dest": "policy_ref",
                "default": None,
                "help": "Optional policy reference for the erasure.",
            },
            {
                "flags": ["--yes"],
                "action": "store_true",
                "default": False,
                "help": "Actually perform the erasure (preview-only without this flag).",
            },
            {"project_arg": True},
        ],
    },
    # ── recover ──
    {
        "name": "recover",
        "help": "Recover a timeline to a known-good anchor event.",
        "handler": "cmd_recover",
        "args": [
            {"name": "slug", "help": "Timeline slug."},
            {
                "flags": ["--at"],
                "required": True,
                "dest": "at_event_id",
                "help": "Event ID (ULID) to recover to (anchor point).",
            },
            {
                "flags": ["--reason"],
                "required": True,
                "help": "Human-readable reason for the recovery.",
            },
            {
                "choice_arg": {
                    "flags": ["--from"],
                    "values": ("supabase",),
                    "dest": "from_backend",
                    "default": None,
                    "help": "Backend to recover on (default: local_fs).",
                }
            },
            {"project_arg": True},
        ],
    },
    # ── branches ──
    {
        "name": "branches",
        "help": "List branches of a timeline (alias for 'branch list').",
        "handler": "cmd_branch_list",
        "args": [
            {
                "name": "source_slug_or_id",
                "help": "Source timeline slug, ULID, or UUID.",
            },
            {"project_arg": True},
        ],
    },
]


# ── Generic table-driven builder ─────────────────────────────────────────────


def _apply_arg_spec(
    parser: argparse.ArgumentParser, spec: dict[str, Any]
) -> None:
    """Apply a single ArgSpec to *parser*.

    Recognised forms (checked in this order):
      - ``project_arg``       → ``_add_project_arg(parser)``
      - ``expected_version_arg`` → ``_add_expected_version_arg(parser)``
      - ``kind_arg``          → ``add_kind_arg(parser, *flags, **rest)``
      - ``choice_arg``        → ``add_choice_arg(parser, *flags, **rest)``
      - ``mutex_group``       → mutually-exclusive group with nested args
      - ``name``              → positional argument
      - ``flags``             → optional argument
    """
    if spec.get("project_arg"):
        _add_project_arg(parser)
    elif spec.get("expected_version_arg"):
        _add_expected_version_arg(parser)
    elif "kind_arg" in spec:
        inner: dict[str, Any] = spec["kind_arg"]
        flags: list[str] = inner["flags"]
        kwargs: dict[str, Any] = {k: v for k, v in inner.items() if k != "flags"}
        add_kind_arg(parser, *flags, **kwargs)
    elif "choice_arg" in spec:
        inner: dict[str, Any] = spec["choice_arg"]
        flags: list[str] = inner["flags"]
        kwargs: dict[str, Any] = {k: v for k, v in inner.items() if k != "flags"}
        add_choice_arg(parser, *flags, **kwargs)
    elif "mutex_group" in spec:
        required: bool = spec.get("mutex_required", False)
        group = parser.add_mutually_exclusive_group(required=required)
        for sub_spec in spec["mutex_group"]:
            _apply_arg_spec(group, dict(sub_spec))
    elif "name" in spec:
        name: str = spec["name"]
        metavar: str | None = spec.get("metavar")
        kwargs: dict[str, Any] = {
            k: v for k, v in spec.items()
            if k not in ("name", "metavar")
        }
        if metavar is not None:
            parser.add_argument(name, metavar=metavar, **kwargs)
        else:
            parser.add_argument(name, **kwargs)
    elif "flags" in spec:
        flags: list[str] = spec["flags"]
        kwargs: dict[str, Any] = {k: v for k, v in spec.items() if k != "flags"}
        parser.add_argument(*flags, **kwargs)
    else:
        raise ValueError(f"Unrecognized ArgSpec: {spec!r}")


def _build_parser_from_table(
    commands: list[dict[str, Any]],
    handler_map: dict[str, Callable[..., Any]],
    subparsers: argparse._SubParsersAction,
) -> None:
    """Walk *commands* and register every (sub)parser onto *subparsers*.

    Handlers are resolved from *handler_map* by name so that the table
    stores strings and callables are looked up at call time (preserving the
    ``.cli`` facade indirection required by monkeypatch contracts).
    """
    for cmd in commands:
        name: str = cmd["name"]
        aliases: list[str] = cmd.get("aliases", [])
        help_text: str = cmd["help"]

        parser = subparsers.add_parser(name, aliases=aliases, help=help_text)

        # Apply argument specs
        for arg_spec in cmd.get("args", []):
            _apply_arg_spec(parser, dict(arg_spec))  # shallow copy — _apply may mutate

        # Recurse into subcommand groups
        if "subcommands" in cmd:
            dest: str = cmd.get("dest", cmd["name"] + "_command")
            subs = parser.add_subparsers(dest=dest, required=True)
            _build_parser_from_table(cmd["subcommands"], handler_map, subs)

        # Attach handler (skip empty handler on group nodes)
        handler_name: str = cmd["handler"]
        if handler_name:
            parser.set_defaults(handler=handler_map[handler_name])


# ── Public entry point ───────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the timeline subcommand parser.

    M4 T12 / P5-4: all command handlers are imported through the ``.cli``
    facade rather than from their canonical modules so that legacy
    monkeypatch seams on ``astrid.core.timeline.cli.cmd_*`` remain
    interceptable.  The handler references in ``_COMMANDS`` are strings
    that get resolved here via ``.cli`` at call time.
    """
    # Late import through the .cli facade — this is the indirection that
    # ~50 tests rely on for monkeypatch.setattr(timeline_cli, "cmd_ls", fake).
    from .timeline import (  # noqa: PLC0415
        # -- cli_edits --
        cmd_arrangement_set,
        cmd_arrangement_show,
        cmd_audio_bind,
        cmd_audio_unbind,
        # -- cli_events --
        cmd_audit,
        # -- cli_backends --
        cmd_branch_create,
        cmd_branch_list,
        cmd_clip_add,
        cmd_clip_annotate,
        cmd_clip_move,
        cmd_clip_remove,
        cmd_clip_replace,
        cmd_clip_retime,
        cmd_clip_retrack,
        cmd_clip_set_text,
        cmd_clip_swap,
        # -- cli_output --
        cmd_cost,
        # -- cli_crud --
        cmd_create,
        cmd_diff,
        cmd_effect_add,
        cmd_effect_remove,
        cmd_effect_tune,
        cmd_erase,
        cmd_export,
        cmd_finalize,
        cmd_history,
        cmd_ls,
        cmd_mass_undo,
        cmd_migrate_events,
        cmd_preview,
        cmd_pull,
        cmd_purge,
        cmd_push,
        cmd_recover,
        cmd_registry_sync,
        cmd_rename,
        cmd_set_default,
        cmd_show,
        cmd_sync,
        cmd_theme_override,
        cmd_theme_set,
        cmd_tombstone,
        cmd_track_add,
        cmd_track_remove,
        cmd_transition_remove,
        cmd_transition_set,
        cmd_undo,
        cmd_who_edited,
    )

    # Build handler lookup from the local names imported above.
    # Every string in _COMMANDS["handler"] must have a key here.
    handler_map: dict[str, Callable[..., Any]] = {
        "cmd_ls": cmd_ls,
        "cmd_create": cmd_create,
        "cmd_show": cmd_show,
        "cmd_rename": cmd_rename,
        "cmd_finalize": cmd_finalize,
        "cmd_tombstone": cmd_tombstone,
        "cmd_purge": cmd_purge,
        "cmd_set_default": cmd_set_default,
        "cmd_export": cmd_export,
        "cmd_cost": cmd_cost,
        "cmd_history": cmd_history,
        "cmd_diff": cmd_diff,
        "cmd_audit": cmd_audit,
        "cmd_preview": cmd_preview,
        "cmd_who_edited": cmd_who_edited,
        "cmd_migrate_events": cmd_migrate_events,
        "cmd_push": cmd_push,
        "cmd_pull": cmd_pull,
        "cmd_registry_sync": cmd_registry_sync,
        "cmd_sync": cmd_sync,
        "cmd_undo": cmd_undo,
        "cmd_mass_undo": cmd_mass_undo,
        "cmd_erase": cmd_erase,
        "cmd_recover": cmd_recover,
        "cmd_branch_create": cmd_branch_create,
        "cmd_branch_list": cmd_branch_list,
        # -- nested subcommands --
        "cmd_clip_add": cmd_clip_add,
        "cmd_clip_remove": cmd_clip_remove,
        "cmd_clip_move": cmd_clip_move,
        "cmd_clip_retrack": cmd_clip_retrack,
        "cmd_clip_retime": cmd_clip_retime,
        "cmd_clip_swap": cmd_clip_swap,
        "cmd_clip_replace": cmd_clip_replace,
        "cmd_clip_set_text": cmd_clip_set_text,
        "cmd_clip_annotate": cmd_clip_annotate,
        "cmd_transition_set": cmd_transition_set,
        "cmd_transition_remove": cmd_transition_remove,
        "cmd_effect_add": cmd_effect_add,
        "cmd_effect_remove": cmd_effect_remove,
        "cmd_effect_tune": cmd_effect_tune,
        "cmd_theme_set": cmd_theme_set,
        "cmd_theme_override": cmd_theme_override,
        "cmd_track_add": cmd_track_add,
        "cmd_track_remove": cmd_track_remove,
        "cmd_audio_bind": cmd_audio_bind,
        "cmd_audio_unbind": cmd_audio_unbind,
        "cmd_arrangement_set": cmd_arrangement_set,
        "cmd_arrangement_show": cmd_arrangement_show,
    }

    parser = RecoverableArgumentParser(
        prog="python3 -m astrid timelines",
        description="Create, inspect, and manage project timelines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _build_parser_from_table(_COMMANDS, handler_map, subparsers)

    return parser
