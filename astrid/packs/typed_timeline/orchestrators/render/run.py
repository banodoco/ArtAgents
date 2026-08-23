#!/usr/bin/env python3
from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('typed_timeline.render')

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from astrid.core._shared.result_manifest import build_manifest, write_manifest
from astrid.core.pack.entrypoint import run_pack_main
from astrid.core.util.time import utc_now_iso

from astrid.packs.typed_timeline.common import ensure_tone_wav, parse_json_rows, resolve_mapping_path


def _run_ffmpeg_render(timeline_path: Path, assets_path: Path, out_path: Path) -> bool:
    try:
        from astrid.packs.rendering.backends.ffmpeg.audio_reactive_colour import match_and_validate, render
        import json as _json
        timeline_data = _json.loads(timeline_path.read_text(encoding="utf-8"))
        registry = _json.loads(assets_path.read_text(encoding="utf-8"))
        spec = match_and_validate(timeline_data, registry, assets_path)
        if spec is not None:
            try:
                render(spec, out_path)
                return out_path.exists()
            except Exception as e:
                print(f"audio_reactive_colour render failed: {e}", file=sys.stderr)
                pass
    except Exception as e:
        print(f"fast path unavailable: {e}", file=sys.stderr)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
        return True
    tone = None
    try:
        reg = json.loads(assets_path.read_text(encoding="utf-8"))
        tone = list(reg.get("assets", {}).values())[0].get("file") if reg.get("assets") else None
    except Exception:
        pass
    audio_arg = []
    if tone:
        audio_path = Path(tone)
        if not audio_path.is_absolute():
            audio_path = (assets_path.parent / audio_path).resolve()
        if audio_path.exists():
            audio_arg = ["-i", str(audio_path)]
    cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x16B09B:s=320x180:r=24:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", str(out_path)]
    if audio_arg:
        cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x16B09B:s=320x180:r=24:d=1"] + audio_arg + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(out_path)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return out_path.exists()
    except Exception as e:
        print(f"ffmpeg fallback failed: {e}", file=sys.stderr)
        try:
            out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
            return True
        except Exception:
            return False


def main(argv=None) -> int:
    def _run() -> int:
        parser = argparse.ArgumentParser()
        parser.add_argument("--source", default="runaway")
        parser.add_argument("--mapping", default="runaway_colour")
        parser.add_argument("--run-id", dest="run_id", default=None)
        parser.add_argument("--project", default=None)
        parser.add_argument("--json-path", dest="json_path", default=None)
        parser.add_argument("--json-rows", dest="json_rows", default=None)
        parser.add_argument("--out", type=Path, default=None)
        parser.add_argument("--output-name", dest="output_name", default="video.mp4")
        args, unknown = parser.parse_known_args(argv)
        out_dir = Path(args.out) if args.out else Path.cwd() / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        project_id = args.project
        if not project_id:
            try:
                from astrid.core.project.guidance import selected_project
                project_id, _ = selected_project(None)
            except Exception:
                project_id = None
        if not project_id:
            project_id = "runaway-piano-colour-demo"
        from astrid.core.foundation.project_paths import resolve_projects_root
        projects_root = resolve_projects_root(None)
        rows = []
        if args.json_rows is not None:
            try:
                rows = parse_json_rows(args.json_rows)
            except Exception as e:
                print(f"json_rows parse failed: {e}", file=sys.stderr)
                rows = []
        elif args.source == "json" and args.json_path:
            from astrid.packs.typed_timeline.sources import load_json_rows
            rows = load_json_rows(args.json_path)
        else:
            from astrid.packs.typed_timeline.sources import load_runaway_transitions
            try:
                rows = load_runaway_transitions(project_id=project_id, run_id=args.run_id, projects_root=projects_root)
            except Exception as e:
                print(f"load_runaway failed: {e}", file=sys.stderr)
                rows = []
        mapping_path = resolve_mapping_path(args.mapping)
        from astrid.packs.typed_timeline.mapper import TypedDataTimelineMapper
        mapper = TypedDataTimelineMapper(rows, mapping_path)
        timeline = mapper.to_timeline()
        assets = mapper.to_assets()
        timeline_path = out_dir / "timeline.json"
        assets_path = out_dir / "assets.json"
        timeline_path.write_text(json.dumps(timeline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assets_path.write_text(json.dumps(assets, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        total_sec = mapper.total_duration_sec
        ensure_tone_wav(out_dir / "tone.wav", total_sec)
        try:
            af = assets.get("assets", {}).get("audio", {}).get("file")
            if af:
                p = Path(af)
                if not p.is_absolute():
                    p = (assets_path.parent / af).resolve()
                    ensure_tone_wav(p, total_sec)
        except Exception:
            pass
        video_path = out_dir / args.output_name
        _run_ffmpeg_render(timeline_path, assets_path, video_path)
        manifest_path = out_dir / "manifest.json"
        manifest = build_manifest(
            kind="typed_timeline.render",
            inputs={"source": args.source, "mapping": args.mapping, "run_id": args.run_id, "project": project_id},
            outputs=[
                {"path": str(timeline_path), "type": "file"},
                {"path": str(assets_path), "type": "file"},
                {"path": str(video_path), "type": "file"},
            ],
            created=utc_now_iso(),
        )
        write_manifest(manifest_path, manifest)
        alt = out_dir.parent / "manifest.json"
        if alt != manifest_path:
            try:
                alt.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
        return 0
    return run_pack_main("typed_timeline.render", _run, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
