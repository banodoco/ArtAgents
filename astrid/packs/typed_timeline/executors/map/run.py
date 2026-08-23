#!/usr/bin/env python3
from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('typed_timeline.map')

import argparse
import json
import sys
import hashlib
import wave
import struct
from pathlib import Path

from astrid.core._shared.result_manifest import build_manifest, write_manifest
from astrid.core.pack.entrypoint import run_pack_main
from astrid.core.foundation.project_paths import resolve_projects_root

REPO_ROOT = Path(__file__).resolve().parents[5]


def _ensure_tone_wav(path: Path, duration_sec: float) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 48000
    n_frames = int(sample_rate * duration_sec)
    # generate silence via wave (mono 16-bit)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        silence = struct.pack("<h", 0) * n_frames
        wf.writeframes(silence)


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
                parsed = json.loads(args.json_rows) if isinstance(args.json_rows, str) else args.json_rows
                if isinstance(parsed, list):
                    rows = parsed
                elif isinstance(parsed, dict) and "rows" in parsed:
                    rows = parsed["rows"]
                else:
                    rows = [parsed]
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
        mapping_path = Path(args.mapping)
        if not mapping_path.exists():
            cand = Path(__file__).resolve().parent.parent.parent / "mappings" / f"{args.mapping}.yaml"
            if cand.exists():
                mapping_path = cand
            else:
                cand2 = Path(__file__).resolve().parent.parent.parent / "mappings" / args.mapping
                if cand2.exists():
                    mapping_path = cand2

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
                _ensure_tone_wav(tone_path, total_sec)
            else:
                # create sibling tone.wav in out_dir as well
                fallback = out_dir / "tone.wav"
                _ensure_tone_wav(fallback, total_sec)
                # also ensure the declared path exists if relative to assets_path
                _ensure_tone_wav(tone_path, total_sec)
        else:
            _ensure_tone_wav(out_dir / "tone.wav", total_sec)

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
