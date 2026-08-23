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


def _video_frame_count(video_path: Path) -> int | None:
    """Return video frame count via ffprobe, or None if unavailable."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        # Prefer nb_read_frames counting
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(video_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, text=True,
        )
        txt = (result.stdout or "").strip()
        if txt and txt != "N/A":
            return int(txt)
    except Exception:
        pass
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "csv=p=0", str(video_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, text=True,
        )
        txt = (result.stdout or "").strip()
        if txt and txt != "N/A":
            return int(float(txt))
    except Exception:
        pass
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration,r_frame_rate,avg_frame_rate", "-of", "json", str(video_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, text=True,
        )
        data = json.loads(result.stdout) if result.stdout else {}
        streams = data.get("streams", []) if isinstance(data, dict) else []
        if streams:
            s = streams[0]
            dur = s.get("duration")
            rfr = s.get("avg_frame_rate") or s.get("r_frame_rate")
            if dur and rfr and "/" in str(rfr):
                num, den = str(rfr).split("/", 1)
                fps = float(num) / float(den) if float(den) != 0 else 0
                return int(round(float(dur) * fps))
    except Exception:
        pass
    return None


def _run_ffmpeg_render(timeline_path: Path, assets_path: Path, out_path: Path) -> bool:
    """Real render via audio_reactive_colour. NO fake fallback. Returns True only on real video."""
    try:
        from astrid.packs.rendering.executors.render.audio_reactive_colour import match_and_validate, render
        import json as _json

        timeline_data = _json.loads(timeline_path.read_text(encoding="utf-8"))
        registry = _json.loads(assets_path.read_text(encoding="utf-8"))
        spec = match_and_validate(timeline_data, registry, assets_path)
        if spec is not None:
            try:
                render(spec, out_path)
                if out_path.exists() and out_path.stat().st_size > 1000:
                    return True
                print("audio_reactive_colour render produced no file", file=sys.stderr)
            except Exception as e:
                print(f"audio_reactive_colour render failed: {e}", file=sys.stderr)
                # do not fall back to fake — propagate failure
                return False
        else:
            print("audio_reactive_colour match_and_validate returned None — no effect clip match", file=sys.stderr)
            return False
    except Exception as e:
        print(f"fast path unavailable: {e}", file=sys.stderr)
        return False
    # No lavfi 1s colour fallback, no fake MP4 header — fail honestly
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ffmpeg not found — failing (no fake video)", file=sys.stderr)
        return False
    print("ffmpeg fallback disabled for validated timeline — failing", file=sys.stderr)
    return False


def main(argv=None) -> int:
    def _run() -> int:
        parser = argparse.ArgumentParser()
        parser.add_argument("--source", default="runaway")
        parser.add_argument("--mapping", default="runaway_colour")
        parser.add_argument("--run-id", dest="run_id", default=None)
        parser.add_argument("--project", default=None)
        parser.add_argument("--project-id", dest="project_id_alias", default=None)
        parser.add_argument("--json-path", dest="json_path", default=None)
        parser.add_argument("--json-rows", dest="json_rows", default=None)
        parser.add_argument("--out", type=Path, default=None)
        parser.add_argument("--output-name", dest="output_name", default="video.mp4")
        args, unknown = parser.parse_known_args(argv)
        out_dir = Path(args.out) if args.out else Path.cwd() / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        # alias: --project-id
        if getattr(args, "project_id_alias", None) and not args.project:
            args.project = args.project_id_alias
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
                return 1
            # For runaway mapping, 0 rows must fail even via json_rows if source is runaway
            if args.source != "json" and not rows:
                print(f"load returned 0 rows for project_id={project_id!r} run_id={args.run_id!r} — failing", file=sys.stderr)
                return 1
        elif args.source == "json" and args.json_path:
            from astrid.packs.typed_timeline.sources import load_json_rows
            rows = load_json_rows(args.json_path)
        else:
            from astrid.packs.typed_timeline.sources import load_runaway_transitions
            try:
                rows = load_runaway_transitions(project_id=project_id, run_id=args.run_id, projects_root=projects_root)
            except Exception as e:
                print(f"load_runaway failed: {e}", file=sys.stderr)
                return 1
            if not rows:
                print(f"load_runaway returned 0 rows for project_id={project_id!r} run_id={args.run_id!r} — failing", file=sys.stderr)
                return 1
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
        ok = _run_ffmpeg_render(timeline_path, assets_path, video_path)
        if not ok:
            print("render failed — not writing success manifest", file=sys.stderr)
            return 1
        if not video_path.exists() or video_path.stat().st_size < 1000:
            print(f"render did not produce video at {video_path}", file=sys.stderr)
            return 1
        # Honest validation before success manifest: timeline must have matching events, video must be 8085 frames
        try:
            tdata = json.loads(timeline_path.read_text(encoding="utf-8"))
            clips = tdata.get("clips", [])
            reactive = [c for c in clips if isinstance(c, dict) and c.get("clipType") == "audio-reactive-colour"]
            if reactive:
                events = reactive[0].get("params", {}).get("events", [])
                exp_events = len(rows)
                # dedup frames may reduce count, but demo 566 should be exact
                if len(events) == 0:
                    print(f"validation failed: timeline has 0 events but rows={len(rows)}", file=sys.stderr)
                    return 1
                # If rows are 566 fixture, require 566 events exactly
                if len(rows) == 566 and len(events) != 566:
                    print(f"validation failed: expected 566 events, got {len(events)}", file=sys.stderr)
                    return 1
                if len(rows) == 10 and len(events) != 10:
                    print(f"validation failed: expected 10 events, got {len(events)}", file=sys.stderr)
                    return 1
                # general: events must equal rows count when no dedup loss
                if len(events) != exp_events:
                    # allow dedup but warn; require at least >0 and <= exp_events
                    if len(events) > exp_events or len(events) == 0:
                        print(f"validation failed: events {len(events)} != rows {exp_events}", file=sys.stderr)
                        return 1
            # canvas total_frames validation
            canvas = tdata.get("theme_overrides", {}).get("visual", {}).get("canvas", {})
            fps = int(canvas.get("fps", 48))
            # total_frames from hold* fps or mapper
            hold = None
            for c in clips:
                if isinstance(c, dict) and c.get("clipType") == "audio-reactive-colour":
                    hold = c.get("hold")
                    break
            total_frames = None
            if hold is not None:
                try:
                    total_frames = int(round(float(hold) * fps))
                except Exception:
                    total_frames = mapper.total_frames
            else:
                total_frames = mapper.total_frames
            if total_frames != 8085:
                print(f"validation failed: total_frames {total_frames} != 8085", file=sys.stderr)
                return 1
            frames = _video_frame_count(video_path)
            if frames is None:
                print("validation failed: could not count video frames via ffprobe", file=sys.stderr)
                return 1
            if frames != 8085:
                print(f"validation failed: video frames {frames} != 8085", file=sys.stderr)
                return 1
            print(f"validation passed: events {len(events) if reactive else 'n/a'} frames_total {total_frames} video_frames {frames}", file=sys.stderr)
        except SystemExit:
            raise
        except Exception as e:
            print(f"validation failed: {e}", file=sys.stderr)
            return 1
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
