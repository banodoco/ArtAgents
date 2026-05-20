#!/usr/bin/env python3
"""Push a locally-materialized hype timeline into a reigh-app row.
from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('builtin.open_in_reigh')


**m3.5 bridge seam**: pre-m6 behavior emits compatibility export and bridge
metadata only.  Post-m6 replay seam: read LocalFs events, replay into Supabase
via ``append_timeline_event`` once m6 Supabase RPC exists.  This pack is the
explicit LocalFs-to-Supabase bridge — no other pack or executor path writes
directly to Supabase.

SD-009 / FLAG-012 — auth scope: this CLI helper writes a user-owned row, so by
default it authenticates with the user's PAT (``REIGH_PAT``) rather than the
worker-only service-role key.  The DataProvider's optimistic-versioning path
still applies; ``--force`` skips the version check (logged WARNING) for
operators who know what they're doing.

Escape hatches preserved from the pre-T7 helper:

* ``--print-sql`` emits an ``INSERT ... ON CONFLICT`` template for the
  Supabase SQL editor (no network).
* ``--copy-to`` / probe-based file copy keeps the byte-preserved file handoff
  for reigh-app's file-based demo dirs.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from ....timeline import Timeline


DEFAULT_REIGH_APP = Path("/Users/peteromalley/Documents/reigh-workspace/reigh-app")
PROBE_DIRS = ("public/timelines", "public/demos", "timelines", "demos")


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "open_in_reigh: the explicit LocalFs-to-Supabase bridge (m3.5). "
            "Pre-m6: emits bridge metadata only. "
            "Post-m6: reads LocalFs events and replays into Supabase via append_timeline_event."
        ),
        epilog=(
            "Pre-m6 behavior: emits compatibility export + bridge metadata only. "
            "No SupabaseDataProvider.save_timeline() call is made — the actual "
            "Supabase push is deferred to m6. "
            "--print-sql and --copy-to are escape hatches: "
            "they skip the network entirely and emit a SQL template / byte-preserved file copies."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out", type=Path, required=True, help="Directory containing hype.timeline.json and hype.assets.json.")
    parser.add_argument("--timeline-id", required=True, help="UUID for public.timelines.id (used in bridge metadata).")
    parser.add_argument("--project-id", help="reigh-app project UUID. Required for bridge metadata emission (skipped for --print-sql / --copy-to / --copy-files).")
    parser.add_argument("--reigh-app", type=Path, default=DEFAULT_REIGH_APP, help=f"Path to the reigh-app checkout for --copy-files probing. Default: {DEFAULT_REIGH_APP}")
    parser.add_argument("--copy-to", type=Path, help="Byte-preserved file copy: copy the JSON files into this directory.")
    parser.add_argument("--copy-files", action="store_true", help="Probe reigh-app for a file-based demo dir and copy hype.timeline.json/hype.assets.json there.")
    parser.add_argument("--name", default="hype", help="Name used when probing a file-based demo folder.")
    parser.add_argument("--print-sql", action="store_true", help="Print an UPSERT template for public.timelines instead of pushing via the DataProvider.")
    parser.add_argument("--dry-run", action="store_true", help="Show the intended action without writing files or making network calls.")
    parser.add_argument("--force", action="store_true", help="Skip optimistic-version check (logged WARNING).")
    parser.add_argument("--service-role", action="store_true", help="Worker-only escape hatch: authenticate via REIGH_SUPABASE_SERVICE_ROLE_KEY instead of REIGH_PAT. Avoid for ownership-bound CLI calls.")
    return parser


def source_paths(out_dir):
    timeline_path = out_dir.resolve() / "hype.timeline.json"
    assets_path = out_dir.resolve() / "hype.assets.json"
    missing = [str(path) for path in (timeline_path, assets_path) if not path.is_file()]
    if missing:
        print(f"open_in_reigh.py: missing required output file(s): {', '.join(missing)}", file=sys.stderr)
        return None, None
    return timeline_path, assets_path


def probe_target(args):
    if args.copy_to:
        return args.copy_to.resolve()
    base = args.reigh_app.resolve()
    for rel in PROBE_DIRS:
        candidate = base / rel
        if candidate.is_dir():
            return candidate / args.name
    return None


def print_copy_plan(timeline_path, assets_path, target, dry_run):
    label = "Would copy" if dry_run else "Copied"
    print(f"{label} {timeline_path} -> {target / timeline_path.name}")
    print(f"{label} {assets_path} -> {target / assets_path.name}")
    print("Reminder: reigh-app's live editor reads timeline rows from Supabase public.timelines, not these copied files.")


def maybe_copy_files(timeline_path, assets_path, target, dry_run):
    if target is None:
        return
    print_copy_plan(timeline_path, assets_path, target, dry_run)
    if dry_run:
        return
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(timeline_path, target / timeline_path.name)
    shutil.copyfile(assets_path, target / assets_path.name)


def print_manual_handoff():
    print(
        "\n".join(
            [
                "No file-backed reigh-app import directory was found.",
                "reigh-app stores timeline data in public.timelines rows with config + asset_registry columns.",
                "Provider reference: reigh-app/src/tools/video-editor/data/SupabaseDataProvider.ts",
                "Manual handoff options:",
                "1. Paste the SQL below into the Supabase dashboard SQL editor after filling <PROJECT_ID> and <USER_ID>.",
                "2. Rerun with --print-sql for the ready INSERT ... ON CONFLICT statement.",
                "3. Rerun with --copy-to DIR if you still want byte-preserved file copies for reference.",
                "ASSET PATH LIMITATION:",
                "hype.assets.json contains local absolute paths from cut.py.",
                "SupabaseDataProvider resolves asset `file` values only as HTTP URLs or timeline-assets bucket keys.",
                "Upload media to the timeline-assets bucket or self-host it, then update each asset `file` value before the timeline will play.",
            ]
        )
    )


def load_json_blob(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_timeline_blob(path):
    return Timeline.load(path).to_json_data()


def sql_json_literal(obj):
    return json.dumps(obj, ensure_ascii=False).replace("'", "''")


def print_sql(args, timeline_path, assets_path):
    timeline_blob = sql_json_literal(load_timeline_blob(timeline_path))
    assets_blob = sql_json_literal(load_json_blob(assets_path))
    safe_name = args.name.replace("'", "''")
    print("SQL template only: fill <PROJECT_ID> and <USER_ID> yourself. This bridge does NOT open a Supabase connection.")
    print(
        "INSERT INTO public.timelines (id, config, asset_registry, project_id, user_id, name) "
        f"VALUES ('{args.timeline_id}', '{timeline_blob}'::jsonb, '{assets_blob}'::jsonb, '<PROJECT_ID>', '<USER_ID>', '{safe_name}') "
        "ON CONFLICT (id) DO UPDATE SET config = EXCLUDED.config, asset_registry = EXCLUDED.asset_registry;"
    )


def push_via_data_provider(args, timeline_path):
    """Emit bridge metadata for the timeline (m3.5 bridge seam).

    Pre-m6 behavior: emits compatibility export + bridge metadata only.
    Post-m6 replay seam: read LocalFs events, replay into Supabase via
    ``append_timeline_event`` once m6 Supabase RPC exists.

    This function does NOT call ``SupabaseDataProvider.save_timeline()``.
    The actual Supabase push is deferred to m6.
    """
    if not args.project_id:
        print(
            "open_in_reigh: --project-id is required for bridge metadata. "
            "Use --print-sql, --copy-to, or --copy-files to skip the network.",
            file=sys.stderr,
        )
        return 2

    new_timeline = load_timeline_blob(timeline_path)
    if not isinstance(new_timeline, dict):
        print("open_in_reigh: timeline JSON must be a JSON object", file=sys.stderr)
        return 2
    if "placements" in new_timeline:
        print(
            "open_in_reigh: refusing to bridge placement-style timeline.json to reigh-app. "
            "The DataProvider expects the canonical clip-shaped TimelineConfig "
            "(per @banodoco/timeline-schema). Re-export with the collapsed schema first.",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(
            f"Would emit bridge metadata for timeline_id={args.timeline_id} "
            f"project_id={args.project_id} (post-m6 replay via open_in_reigh)"
        )
        return 0

    # Emit bridge metadata — no SupabaseDataProvider.save_timeline() call.
    import time as _time
    bridge = {
        "bridge": "open_in_reigh",
        "schema_version": 1,
        "project_id": args.project_id,
        "timeline_id": args.timeline_id,
        "timeline_path": str(timeline_path.resolve()),
        "note": (
            "Bridge metadata for m6 replay.  When m6 Supabase RPC is available, "
            "open_in_reigh will read LocalFs events and replay them into Supabase "
            "via append_timeline_event.  No direct save_timeline call is made here."
        ),
        "emitted_at": _time.time(),
    }
    print(json.dumps(bridge, separators=(",", ":"), sort_keys=True))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    timeline_path, assets_path = source_paths(args.out)
    if timeline_path is None or assets_path is None:
        return 1

    # Escape hatches: --print-sql and --copy-to / --copy-files / probe.
    handled_offline = False
    if args.copy_to is not None or args.copy_files:
        target = probe_target(args)
        if target is not None:
            maybe_copy_files(timeline_path, assets_path, target, args.dry_run)
            handled_offline = True
        elif args.copy_to is not None:
            # User asked for a copy but the dir wasn't writable (probe_target only
            # returns None when --copy-to is missing AND no probe match found).
            handled_offline = True
        else:
            print_manual_handoff()
            handled_offline = True

    if args.print_sql:
        print_sql(args, timeline_path, assets_path)
        handled_offline = True

    if handled_offline:
        return 0

    return push_via_data_provider(args, timeline_path)


if __name__ == "__main__":
    raise SystemExit(main())
