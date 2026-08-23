#!/usr/bin/env python3
from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('typed_timeline.map')

import argparse
import json
import sys
from pathlib import Path

from astrid.core._shared.result_manifest import build_manifest, write_manifest
from astrid.core.pack.entrypoint import run_pack_main
from astrid.core.foundation.project_paths import resolve_projects_root

from astrid.packs.typed_timeline.common import ensure_tone_wav, parse_json_rows, resolve_mapping_path



def main(argv=None) -> int:
    def _run() -> int:
        parser = argparse.ArgumentParser()
        parser.add_argument("--source", required=True)
        parser.add_argument("--mapping", required=True)
        parser.add_argument("--out", required=True, type=Path)
        parser.add_argument("--run-id", dest="run_id", default=None)
        parser.add_argument("--project", default=None)
        parser.add_argument("--json-path", dest="json_path", default=None)
        parser.add_argument("--json-rows", dest="json_rows", default=None)
        args = parser.parse_args(argv)

        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        # resolve project
        from astrid.core.foundation.project_paths import resolve_projects_root
        projects_root = resolve_projects_root(None)
        # project from flag or env selection
        project_id = args.project
        if project_id is None:
            # try to get from ASTRID selected project?
            try:
                from astrid.core.project.guidance import selected_project
                project_id, _ = selected_project(None)
            except Exception:
                project_id = None
        # fallback to env or default used in tests
        if not project_id:
            project_id = "runaway-piano-colour-demo"

        # load rows
        rows = []
        if args.json_rows is not None:
            try:
                rows = parse_json_rows(args.json_rows)
            except Exception as e:
                print(f"failed to parse json_rows: {e}", file=sys.stderr)
                return 1
        elif args.source == "json" and args.json_path:
            from astrid.packs.typed_timeline.sources import load_json_rows
            rows = load_json_rows(args.json_path)
        else:
            # runaway source
            from astrid.packs.typed_timeline.sources import load_runaway_transitions
            try:
                rows = load_runaway_transitions(project_id=project_id, run_id=args.run_id, projects_root=projects_root)
            except Exception as e:
                # if DB empty, fall back to 0 rows
                print(f"load_runaway failed: {e}", file=sys.stderr)
                rows = []

        # resolve mapping
        mapping_path = resolve_mapping_path(args.mapping)

        from astrid.packs.typed_timeline.mapper import TypedDataTimelineMapper

        mapper = TypedDataTimelineMapper(rows, mapping_path)
        timeline = mapper.to_timeline()
        assets = mapper.to_assets()

        timeline_path = out_dir / "timeline.json"
        assets_path = out_dir / "assets.json"
        timeline_path.write_text(json.dumps(timeline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assets_path.write_text(json.dumps(assets, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # ensure tone.wav for audio-reactive path
        total_sec = mapper.total_duration_sec
        # assets file entry file is tone.wav relative to assets_path
        assets_file = assets.get("assets", {}).get("audio", {}).get("file") if isinstance(assets.get("assets"), dict) else None
        if assets_file:
            tone_path = (assets_path.parent / assets_file).resolve() if not Path(assets_file).is_absolute() else Path(assets_file)
            # if tone_path is inside out_dir, ensure it
            if str(tone_path).startswith(str(out_dir.resolve())) or tone_path.parent == out_dir.resolve():
                ensure_tone_wav(tone_path, total_sec)
            else:
                # create sibling tone.wav in out_dir as well
                fallback = out_dir / "tone.wav"
                ensure_tone_wav(fallback, total_sec)
                # also ensure the declared path exists if relative to assets_path
                ensure_tone_wav(tone_path, total_sec)
        else:
            ensure_tone_wav(out_dir / "tone.wav", total_sec)

        # write manifest
        manifest_path = out_dir / "manifest.json"
        # also staging fallback
        from astrid.core.util.time import utc_now_iso
        manifest = build_manifest(
            kind="typed_timeline.map",
            inputs={"source": args.source, "mapping": args.mapping, "run_id": args.run_id, "project": project_id},
            outputs=[
                {"path": str(timeline_path), "type": "file"},
                {"path": str(assets_path), "type": "file"},
            ],
            created=utc_now_iso(),
        )
        # include tone.wav if exists
        tone_candidate = out_dir / "tone.wav"
        if tone_candidate.exists():
            manifest["outputs"].append({"path": str(tone_candidate), "type": "file"})

        write_manifest(manifest_path, manifest)
        # also write to staging_dir / manifest.json for handler discovery fallback
        alt = out_dir.parent / "manifest.json"
        if alt != manifest_path:
            try:
                alt.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
        return 0

    return run_pack_main("typed_timeline.map", _run, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
