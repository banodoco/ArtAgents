#!/usr/bin/env python3

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('rendering.render')


import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from astrid.core.audit import AuditContext
from astrid.core import timeline
from astrid.core.subprocess_env import build_child_subprocess_env
from astrid.packs.training.executors.asset_cache import run as asset_cache
from astrid.core.paths import REPO_ROOT, WORKSPACE_ROOT
from astrid.core.theme import load_theme


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with HTTP Range support.

    Remotion's media components seek into long source videos via Range
    requests. Without this, a 2-hour source video gets fully downloaded
    on every seek, which either times out or renders as black/silence.
    """

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Quiet the access log; one line per clip byte fetch is noise.
        return

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        try:
            fs = os.fstat(f.fileno())
        except OSError:
            f.close()
            self.send_error(500, "File stat failed")
            return None
        size = fs.st_size
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            try:
                start_s, end_s = range_header[6:].split("-", 1)
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else size - 1
                if start < 0 or end >= size or start > end:
                    raise ValueError
            except ValueError:
                f.close()
                self.send_error(416, "Invalid Range")
                return None
            length = end - start + 1
            f.seek(start)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            self._range_limit = length
            return f
        self._range_limit = None
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile) -> None:
        limit = getattr(self, "_range_limit", None)
        if limit is None:
            try:
                super().copyfile(source, outputfile)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        remaining = limit
        chunk = 64 * 1024
        try:
            while remaining > 0:
                buf = source.read(min(chunk, remaining))
                if not buf:
                    break
                outputfile.write(buf)
                remaining -= len(buf)
        except (BrokenPipeError, ConnectionResetError):
            pass


def _accepts_ranges(url: str) -> bool:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.headers.get("Accept-Ranges", "").lower() == "bytes"
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _parse_url_expiry(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _classify_assets(assets_path: Path) -> dict[str, dict[str, object]]:
    if not assets_path.exists():
        raise FileNotFoundError("hype.assets.json missing — did you run cut.py first?")
    registry = timeline.load_registry(assets_path)
    classified: dict[str, dict[str, object]] = {}
    now = datetime.now(timezone.utc)
    for key, entry in registry["assets"].items():
        url = entry.get("url")
        expires_at = entry.get("url_expires_at")
        if isinstance(expires_at, str) and _parse_url_expiry(expires_at) <= now:
            raise RuntimeError(f"Asset {key} URL expired at {expires_at}; refresh upstream before rendering")
        if isinstance(url, str):
            if _accepts_ranges(url):
                classified[key] = {"mode": "url-direct", "url": url, "local_path": None}
            else:
                classified[key] = {
                    "mode": "url-fetched",
                    "url": url,
                    "local_path": Path(asset_cache.fetch(url, expected_sha256=entry.get("content_sha256"))),
                }
            continue
        file_value = entry.get("file")
        if not isinstance(file_value, str) or not file_value:
            raise FileNotFoundError(f"Asset '{key}' has no file path or URL")
        local_path = Path(file_value)
        if not local_path.is_absolute():
            local_path = (assets_path.parent / local_path).resolve()
        classified[key] = {"mode": "local", "url": None, "local_path": local_path}
    return classified


def _server_root_for(assets_path: Path, classified: dict[str, dict[str, object]]) -> Path:
    """Pick a serve root that contains every asset file.

    Uses the common parent of all absolute asset paths. Callers must ensure
    every asset resolves under this root before URL rewriting.
    """
    resolved_paths: list[Path] = []
    for entry in classified.values():
        if entry.get("mode") == "url-direct":
            continue
        local_path = entry.get("local_path")
        if isinstance(local_path, Path):
            resolved_paths.append(local_path.resolve())
    if not resolved_paths:
        return assets_path.parent
    common = Path(os.path.commonpath([str(p) for p in resolved_paths]))
    return common if common.is_dir() else common.parent


def _warn_cross_project_assets(classified: dict[str, dict[str, object]]) -> None:
    owner = os.environ.get("ASTRID_GATEWAY_RESOLVED_PROJECT")
    if not owner:
        return
    try:
        from astrid.core.project.paths import resolve_projects_root

        projects_root = resolve_projects_root().resolve()
    except Exception:
        return
    warned: set[tuple[str, str]] = set()
    for asset_key, entry in classified.items():
        local_path = entry.get("local_path")
        if not isinstance(local_path, Path):
            continue
        try:
            relative = local_path.resolve(strict=False).relative_to(projects_root)
        except ValueError:
            continue
        if not relative.parts:
            continue
        asset_project = relative.parts[0]
        if asset_project == owner:
            continue
        marker = (str(asset_key), asset_project)
        if marker in warned:
            continue
        warned.add(marker)
        print(
            "rendering.render: warning: "
            f"asset {asset_key!r} is from project {asset_project!r} "
            f"while the render is owned by project {owner!r}; "
            "keeping the owner project unchanged.",
            file=sys.stderr,
        )


def _swap_from_dump(clip: dict) -> dict:
    out = dict(clip)
    if "from_" in out:
        out["from"] = out.pop("from_")
    return out


def _resolve_assets(
    assets_path: Path,
    server_root: Path,
    server_port: int,
    classified: dict[str, dict[str, object]],
) -> dict:
    # Remotion's bundler would copy the entire --public-dir into the webpack
    # bundle, which explodes disk usage for large source videos. We serve
    # assets over HTTP from their original location instead — Remotion's
    # <Video src> accepts http:// URLs natively and streams without copying.
    if not assets_path.exists():
        raise FileNotFoundError("hype.assets.json missing — did you run cut.py first?")
    registry = timeline.load_registry(assets_path)
    for asset_key, entry in registry["assets"].items():
        asset_info = classified[asset_key]
        if asset_info.get("mode") == "url-direct":
            entry["file"] = entry["url"]
            continue
        local_path = asset_info.get("local_path")
        if not isinstance(local_path, Path):
            raise FileNotFoundError(f"Asset '{asset_key}' has no local path")
        resolved = local_path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Asset '{asset_key}' resolved to missing file: {resolved}")
        try:
            rel = resolved.relative_to(server_root)
        except ValueError as err:
            raise RuntimeError(
                f"Asset '{asset_key}' at {resolved} is not inside server root {server_root}; "
                "all assets must share a common parent directory"
            ) from err
        entry["file"] = f"http://localhost:{server_port}/{rel.as_posix()}"
    return registry


def _validate_project_dir(project_dir: Path) -> None:
    if not project_dir.exists():
        raise FileNotFoundError(f"Remotion project directory not found: {project_dir}")
    package_json = project_dir / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"Remotion project is missing package.json: {package_json}")
    node_modules = project_dir / "node_modules"
    if not node_modules.exists():
        raise FileNotFoundError(
            "Run `npm install` in tools/remotion/ first; "
            "see docs/reference/render-adapter.md for @banodoco adapter package install instructions"
        )

    # Fail closed if any required @banodoco adapter package is missing.
    # These packages are adapter-installed (GitHub tarball), not published
    # to a public npm registry.  See docs/reference/render-adapter.md (SD2).
    banodoco_root = node_modules / "@banodoco"
    _BANODOCO_REQUIRED = (
        "timeline-composition",
        "timeline-schema",
        "timeline-theme-2rp",
    )
    missing: list[str] = []
    for pkg in _BANODOCO_REQUIRED:
        pkg_dir = banodoco_root / pkg
        if not pkg_dir.is_dir():
            missing.append(f"@banodoco/{pkg}")
    if missing:
        raise FileNotFoundError(
            f"Missing @banodoco render package(s): {', '.join(missing)}. "
            f"These packages are adapter-required and not published to a public npm registry. "
            f"See docs/reference/render-adapter.md for adapter install instructions."
        )


def _serialize_timeline(timeline_path: Path, *, default_theme: str = "banodoco-default") -> dict:
    return timeline.Timeline.load(timeline_path).for_render(default_theme=default_theme).to_json_data()


def _resolve_theme_path(theme_path: Path) -> Path:
    if theme_path.name == "theme.json":
        return theme_path
    if theme_path.exists() and theme_path.is_dir():
        return theme_path / "theme.json"
    if theme_path.exists():
        return theme_path
    return WORKSPACE_ROOT / "themes" / str(theme_path) / "theme.json"


def _theme_for_props(theme_path: Path) -> dict:
    resolved = _resolve_theme_path(theme_path)
    if not resolved.exists():
        return {
            "id": "banodoco-default",
            "visual": {
                "color": {
                    "fg": "#ffffff",
                    "bg": "#000000",
                    "accent": "#ffffff",
                },
                "type": {
                    "families": {"heading": "Georgia, serif", "body": "Georgia, serif"},
                    "size": {"base": 64, "small": 36, "large": 96},
                    "weight": {"normal": 400, "bold": 700},
                    "lineHeight": 1.1,
                },
                "motion": {"fadeMs": 250},
                "canvas": {
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                },
            },
        }
    theme = load_theme(resolved)
    return {"id": theme["id"], "visual": theme["visual"]}


def _theme_slug_for_render_default(theme_path: Path) -> str:
    resolved = _resolve_theme_path(theme_path)
    if resolved.name == "theme.json":
        return resolved.parent.name
    return resolved.stem or "banodoco-default"


def _resolved_theme_for_render(timeline_path: Path, fallback_theme_path: Path) -> dict:
    """Resolve the timeline's theme + theme_overrides into the props-shaped dict.

    The timeline references a theme by slug; per-run overrides live in
    timeline.theme_overrides. We merge them and trim to {id, visual} for Remotion
    props.
    """
    loaded = timeline.Timeline.load(timeline_path)
    render_view = loaded.for_render(default_theme=_theme_slug_for_render_default(fallback_theme_path))
    timeline_config = loaded.to_config()
    timeline_config.setdefault("theme", render_view.theme)
    repo_themes_root = REPO_ROOT / "themes"
    themes_root = repo_themes_root if repo_themes_root.exists() else WORKSPACE_ROOT / "themes"
    try:
        merged = timeline.resolve_timeline_theme(timeline_config, themes_root)
    except (FileNotFoundError, ValueError):
        merged = None
    if not isinstance(merged, dict) or "visual" not in merged:
        # Caller-supplied --theme path is the fallback when the timeline can't be
        # resolved (e.g. running against a stripped fixture).
        return _theme_for_props(fallback_theme_path)
    return {"id": merged.get("id") or merged.get("visual", {}).get("id") or "theme", "visual": merged["visual"]}


def _timeline_canvas(timeline_data: dict) -> tuple[int, int, int]:
    canvas = timeline_data.get("theme_overrides", {}).get("visual", {}).get("canvas", {})
    return (
        int(canvas.get("width", 1920)),
        int(canvas.get("height", 1080)),
        int(canvas.get("fps", 30)),
    )


def _clip_duration_seconds(clip: dict) -> float:
    start = float(clip.get("from", 0) or 0)
    end = float(clip.get("to", start) or start)
    speed = float(clip.get("speed", 1) or 1)
    if speed <= 0:
        raise ValueError(f"Clip {clip.get('id')!r} has non-positive speed {speed}")
    return max(0.0, end - start) / speed


def _clip_timeline_end_seconds(clip: dict) -> float:
    start = float(clip.get("at", 0) or 0)
    if clip.get("clipType") == "media":
        return start + _clip_duration_seconds(clip)
    hold = clip.get("hold")
    if isinstance(hold, (int, float)):
        return start + max(0.0, float(hold))
    if isinstance(clip.get("to"), (int, float)):
        return float(clip["to"])
    return start


def _timeline_duration_seconds(timeline_data: dict) -> float:
    metadata = timeline_data.get("metadata", {})
    explicit = metadata.get("duration_seconds") if isinstance(metadata, dict) else None
    if not isinstance(explicit, (int, float)) and isinstance(metadata, dict):
        explicit = metadata.get("expected_duration_seconds")
    if isinstance(explicit, (int, float)):
        return float(explicit)
    return max((_clip_timeline_end_seconds(clip) for clip in timeline_data.get("clips", [])), default=0.0)


def _round_frame_time(seconds: float, fps: int, *, mode: str) -> float:
    frames = seconds * fps
    if mode == "floor":
        frame = int(frames // 1)
    elif mode == "ceil":
        frame = int(-(-frames // 1))
    else:
        frame = round(frames)
    return frame / fps


def _clip_overlaps(clip: dict, start: float, end: float) -> bool:
    clip_start = float(clip.get("at", 0) or 0)
    clip_end = _clip_timeline_end_seconds(clip)
    return clip_start < end and clip_end > start


def _window_clip(clip: dict, start: float, end: float) -> dict | None:
    if not _clip_overlaps(clip, start, end):
        return None
    clip_start = float(clip.get("at", 0) or 0)
    visible_start = max(clip_start, start)
    visible_end = min(_clip_timeline_end_seconds(clip), end)
    if visible_end <= visible_start:
        return None

    out = dict(clip)
    out["at"] = visible_start - start
    out["id"] = f"{clip.get('id', 'clip')}_{start:.3f}_{end:.3f}".replace(".", "_")
    if clip.get("clipType") == "media":
        speed = float(clip.get("speed", 1) or 1)
        source_from = float(clip.get("from", 0) or 0) + ((visible_start - clip_start) * speed)
        out["from"] = source_from
        out["to"] = source_from + ((visible_end - visible_start) * speed)
    elif isinstance(clip.get("hold"), (int, float)):
        out["hold"] = visible_end - visible_start
    return out


def _window_timeline_data(timeline_data: dict, start: float, end: float, *, media_only: bool) -> dict:
    clips: list[dict] = []
    for clip in timeline_data.get("clips", []):
        if media_only and clip.get("clipType") != "media":
            continue
        windowed = _window_clip(clip, start, end)
        if windowed is not None:
            clips.append(windowed)
    used_tracks = {clip.get("track") for clip in clips}
    tracks = [track for track in timeline_data.get("tracks", []) if track.get("id") in used_tracks]
    out = dict(timeline_data)
    out["tracks"] = tracks
    out["clips"] = clips
    out["metadata"] = {
        **dict(timeline_data.get("metadata", {})),
        "source_window_start_seconds": start,
        "source_window_end_seconds": end,
        "duration_seconds": end - start,
    }
    return out


def _validate_ffmpeg_media_timeline(timeline_data: dict) -> None:
    tracks = {track.get("id"): track for track in timeline_data.get("tracks", [])}
    visual_tracks = [track for track in tracks.values() if track.get("kind") == "visual"]
    audio_tracks = [track for track in tracks.values() if track.get("kind") == "audio"]
    if len(visual_tracks) != 1:
        raise ValueError("ffmpeg engine supports exactly one visual track")
    for clip in timeline_data.get("clips", []):
        if clip.get("clipType") != "media":
            raise ValueError(f"ffmpeg engine only supports media clips, got {clip.get('clipType')!r}")
        if float(clip.get("speed", 1) or 1) != 1.0:
            raise ValueError("ffmpeg engine does not support speed changes yet")
        track = tracks.get(clip.get("track"), {})
        if track.get("kind") == "visual" and float(clip.get("volume", 0) or 0) != 0:
            raise ValueError("ffmpeg engine expects visual clips to have muted embedded audio")
    audio_track_ids = {track["id"] for track in audio_tracks}
    audio_clips = sorted(
        [clip for clip in timeline_data.get("clips", []) if clip.get("track") in audio_track_ids],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    cursor = 0.0
    for clip in audio_clips:
        at = float(clip.get("at", 0) or 0)
        if at < cursor - 0.001:
            raise ValueError("ffmpeg engine supports multiple audio tracks only when audio clips do not overlap")
        cursor = max(cursor, at + _clip_duration_seconds(clip))


def _render_ffmpeg_media(timeline_path: Path, assets_path: Path, out_path: Path) -> Path:
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
    registry = timeline.load_registry(assets_path)
    _validate_ffmpeg_media_timeline(timeline_data)
    width, height, fps = _timeline_canvas(timeline_data)
    tracks = {track.get("id"): track for track in timeline_data.get("tracks", [])}
    visual_track_ids = {track["id"] for track in tracks.values() if track.get("kind") == "visual"}
    audio_track_ids = {track["id"] for track in tracks.values() if track.get("kind") == "audio"}
    video_clips = sorted(
        [clip for clip in timeline_data.get("clips", []) if clip.get("track") in visual_track_ids],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    audio_clips = sorted(
        [clip for clip in timeline_data.get("clips", []) if clip.get("track") in audio_track_ids],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    if not video_clips:
        raise ValueError("ffmpeg engine needs at least one visual media clip")

    asset_keys: list[str] = []
    for clip in [*video_clips, *audio_clips]:
        asset_key = str(clip.get("asset") or "")
        if not asset_key:
            raise ValueError(f"Clip {clip.get('id')!r} has no asset")
        if asset_key not in registry["assets"]:
            raise ValueError(f"Clip {clip.get('id')!r} references unknown asset {asset_key!r}")
        if asset_key not in asset_keys:
            asset_keys.append(asset_key)

    inputs: list[str] = []
    for asset_key in asset_keys:
        entry = registry["assets"][asset_key]
        file_value = entry.get("file")
        if not isinstance(file_value, str) or not file_value:
            raise ValueError(f"ffmpeg engine requires local file assets; {asset_key!r} has no file")
        asset_path = Path(file_value)
        if not asset_path.is_absolute():
            asset_path = (assets_path.parent / asset_path).resolve()
        inputs.extend(["-i", str(asset_path)])
    asset_index = {asset_key: index for index, asset_key in enumerate(asset_keys)}

    filters: list[str] = []
    video_labels: list[str] = []
    copy_video_input: int | None = None
    if len(video_clips) == 1:
        clip = video_clips[0]
        asset_key = str(clip["asset"])
        entry = registry["assets"][asset_key]
        source_duration = entry.get("duration")
        source_resolution = entry.get("resolution")
        start = float(clip.get("from", 0) or 0)
        end = float(clip.get("to", start) or start)
        at = float(clip.get("at", 0) or 0)
        full_duration = isinstance(source_duration, (int, float)) and abs((end - start) - float(source_duration)) < 0.05
        same_resolution = source_resolution == f"{width}x{height}"
        no_visual_adjustments = not any(
            key in clip
            for key in ("x", "y", "width", "height", "cropTop", "cropBottom", "cropLeft", "cropRight", "effects", "transition")
        )
        if at == 0 and start == 0 and full_duration and same_resolution and no_visual_adjustments:
            copy_video_input = asset_index[asset_key]
    if copy_video_input is None:
        for index, clip in enumerate(video_clips):
            inp = asset_index[str(clip["asset"])]
            start = float(clip.get("from", 0) or 0)
            end = float(clip.get("to", start) or start)
            label = f"v{index}"
            filters.append(
                f"[{inp}:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS,"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                f"fps={fps},format=yuv420p[{label}]"
            )
            video_labels.append(f"[{label}]")
        filters.append("".join(video_labels) + f"concat=n={len(video_labels)}:v=1:a=0[vout]")

    audio_labels: list[str] = []
    cursor = 0.0
    audio_index = 0
    for clip in audio_clips:
        at = float(clip.get("at", 0) or 0)
        if at > cursor + 0.001:
            duration = at - cursor
            label = f"a{audio_index}"
            filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.6f}[{label}]")
            audio_labels.append(f"[{label}]")
            audio_index += 1
        inp = asset_index[str(clip["asset"])]
        start = float(clip.get("from", 0) or 0)
        end = float(clip.get("to", start) or start)
        volume = float(clip.get("volume", 1) or 0)
        label = f"a{audio_index}"
        filters.append(
            f"[{inp}:a]atrim=start={start:.6f}:end={end:.6f},"
            f"asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume={volume:.6f}[{label}]"
        )
        audio_labels.append(f"[{label}]")
        cursor = at + _clip_duration_seconds(clip)
        audio_index += 1
    if not audio_labels:
        duration = sum(_clip_duration_seconds(clip) for clip in video_clips)
        filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.6f}[a0]")
        audio_labels.append("[a0]")
    filters.append("".join(audio_labels) + f"concat=n={len(audio_labels)}:v=0:a=1[aout]")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            f"{copy_video_input}:v:0" if copy_video_input is not None else "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "copy" if copy_video_input is not None else "libx264",
            *(["-preset", "veryfast", "-crf", "20"] if copy_video_input is None else []),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
    )
    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_ffmpeg")
        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_ffmpeg")
        render_id = audit.register_asset(
            kind="render",
            path=out_path,
            label="Rendered video",
            parents=[timeline_id, assets_id],
            stage="render_ffmpeg",
            metadata={"engine": "ffmpeg"},
        )
        audit.register_node(
            stage="render_ffmpeg",
            label="Render media-only timeline with ffmpeg",
            parents=[timeline_id, assets_id],
            outputs=[render_id],
            metadata={"engine": "ffmpeg"},
        )
    return out_path


def _complex_clip_windows(timeline_data: dict, fps: int, *, handle_seconds: float = 0.25) -> list[tuple[float, float]]:
    duration = _timeline_duration_seconds(timeline_data)
    tracks = {track.get("id"): track for track in timeline_data.get("tracks", [])}
    visual_track_ids = {track.get("id") for track in timeline_data.get("tracks", []) if track.get("kind") == "visual"}
    visual_media_coverage: dict[str, float] = {}
    for candidate in timeline_data.get("clips", []):
        if candidate.get("clipType") != "media" or candidate.get("track") not in visual_track_ids:
            continue
        track_id = str(candidate.get("track"))
        visual_media_coverage[track_id] = visual_media_coverage.get(track_id, 0.0) + _clip_duration_seconds(candidate)
    base_visual_track_id = max(visual_media_coverage, key=visual_media_coverage.get) if visual_media_coverage else None
    windows: list[tuple[float, float]] = []
    clips = timeline_data.get("clips", [])
    for index, clip in enumerate(clips):
        media_clip = clip.get("clipType") == "media"
        if media_clip:
            track = tracks.get(clip.get("track"), {})
            params = clip.get("params") if isinstance(clip.get("params"), dict) else {}
            effects = clip.get("effects")
            has_effects = bool(effects)
            has_transition = bool(clip.get("transition"))
            has_overlay_track = track.get("kind") == "visual" and clip.get("track") != base_visual_track_id
            has_opacity = isinstance(clip.get("opacity"), (int, float)) and float(clip.get("opacity") or 0) != 1.0
            has_audio_fade = track.get("kind") == "audio" and (
                isinstance(params.get("fadeIn"), (int, float)) or isinstance(params.get("fadeOut"), (int, float))
            )
            if not (has_effects or has_transition or has_overlay_track or has_opacity or has_audio_fade):
                continue
            next_same_track = next(
                (candidate for candidate in clips[index + 1 :] if candidate.get("track") == clip.get("track")),
                None,
            )
            if has_transition and next_same_track is not None:
                transition = clip.get("transition")
                transition_seconds = 8 / fps
                if isinstance(transition, dict):
                    if isinstance(transition.get("duration"), (int, float)):
                        transition_seconds = float(transition["duration"])
                    elif isinstance(transition.get("durationFrames"), (int, float)):
                        transition_seconds = float(transition["durationFrames"]) / fps
                clip_end = _clip_timeline_end_seconds(clip)
                next_start = float(next_same_track.get("at", clip_end) or clip_end)
                start = max(0.0, min(clip_end - transition_seconds, next_start) - handle_seconds)
                end = min(duration, max(clip_end, next_start + transition_seconds) + handle_seconds)
                if end > start:
                    windows.append(
                        (
                            _round_frame_time(start, fps, mode="floor"),
                            _round_frame_time(end, fps, mode="ceil"),
                        )
                    )
                continue
        start = max(0.0, float(clip.get("at", 0) or 0) - handle_seconds)
        end = min(duration, _clip_timeline_end_seconds(clip) + handle_seconds)
        if end <= start:
            continue
        windows.append(
            (
                _round_frame_time(start, fps, mode="floor"),
                _round_frame_time(end, fps, mode="ceil"),
            )
        )
    if not windows:
        return []
    windows.sort()
    merged: list[tuple[float, float]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _hybrid_segments(timeline_data: dict) -> list[dict[str, float | str]]:
    _width, _height, fps = _timeline_canvas(timeline_data)
    duration = _round_frame_time(_timeline_duration_seconds(timeline_data), fps, mode="ceil")
    complex_windows = _complex_clip_windows(timeline_data, fps)
    if not complex_windows:
        return [{"engine": "ffmpeg", "from": 0.0, "to": duration}]
    segments: list[dict[str, float | str]] = []
    cursor = 0.0
    for start, end in complex_windows:
        start = max(0.0, min(start, duration))
        end = max(start, min(end, duration))
        if start > cursor:
            segments.append({"engine": "ffmpeg", "from": cursor, "to": start})
        if end > start:
            segments.append({"engine": "remotion", "from": start, "to": end})
        cursor = max(cursor, end)
    if cursor < duration:
        segments.append({"engine": "ffmpeg", "from": cursor, "to": duration})
    return [segment for segment in segments if float(segment["to"]) > float(segment["from"])]


def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
    inputs: list[str] = []
    filters: list[str] = []
    concat_inputs: list[str] = []
    for index, path in enumerate(segment_paths):
        inputs.extend(["-i", str(path)])
        filters.append(f"[{index}:v]setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{index}]")
        filters.append(f"[{index}:a]asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[a{index}]")
        concat_inputs.append(f"[v{index}][a{index}]")
    filters.append("".join(concat_inputs) + f"concat=n={len(segment_paths)}:v=1:a=1[vout][aout]")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
    )


def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
    segments = _hybrid_segments(timeline_data)
    if len(segments) == 1 and segments[0]["engine"] == "ffmpeg":
        return _render_ffmpeg_media(timeline_path, assets_path, out_path)

    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(out_path.parent)) as tmp:
        tmp_dir = Path(tmp)
        segment_paths: list[Path] = []
        for index, segment in enumerate(segments):
            engine = str(segment["engine"])
            start = float(segment["from"])
            end = float(segment["to"])
            segment_dir = tmp_dir / f"{index:04d}-{engine}"
            segment_dir.mkdir(parents=True, exist_ok=True)
            segment_timeline_path = segment_dir / "timeline.json"
            segment_out_path = segment_dir / "segment.mp4"
            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
            segment_timeline_path.write_text(json.dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
            if engine == "ffmpeg":
                _render_ffmpeg_media(segment_timeline_path, assets_path, segment_out_path)
            else:
                render(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    engine="remotion",
                    **remotion_kwargs,
                )
            segment_paths.append(segment_out_path)
        _concat_segments(segment_paths, out_path)

    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_hybrid")
        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_hybrid")
        render_id = audit.register_asset(
            kind="render",
            path=out_path,
            label="Rendered video",
            parents=[timeline_id, assets_id],
            stage="render_hybrid",
            metadata={"engine": "hybrid", "segments": segments},
        )
        audit.register_node(
            stage="render_hybrid",
            label="Render hybrid timeline",
            parents=[timeline_id, assets_id],
            outputs=[render_id],
            metadata={"engine": "hybrid", "segments": segments},
        )
    return out_path


def _regenerate_element_registries(project_dir: Path, theme_path: Path | None) -> None:
    generator = REPO_ROOT / "scripts" / "gen_effect_registry.py"
    cmd = [sys.executable, str(generator)]
    if theme_path is not None:
        cmd.extend(["--theme", str(_resolve_theme_path(theme_path))])
    env: dict[str, str] = {}
    composition_src = project_dir / "node_modules" / "@banodoco" / "timeline-composition" / "typescript" / "src"
    if composition_src.is_dir():
        env["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
    subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=build_child_subprocess_env(explicit_env=env),
        capture_output=True,
        check=True,
        text=True,
    )


def _stderr_tail(stderr: str) -> str:
    lines = stderr.splitlines()
    tail = lines[-40:] if len(lines) > 40 else lines
    return "\n".join(tail).strip()


def _require_free_space(path: Path, min_free_gb: float | None) -> None:
    if min_free_gb is None or min_free_gb <= 0:
        return
    target = path if path.exists() else path.parent
    usage = shutil.disk_usage(target)
    min_free = int(min_free_gb * 1024 * 1024 * 1024)
    if usage.free < min_free:
        free_gb = usage.free / (1024 * 1024 * 1024)
        raise RuntimeError(
            f"Remotion render needs at least {min_free_gb:.1f} GiB free at {target}; "
            f"only {free_gb:.1f} GiB is available"
        )


def render(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    engine: str = "remotion",
    project_dir: Path | None = None,
    composition_id: str = "TimelineComposition",
    theme_path: Path | None = None,
    min_free_gb: float | None = None,
) -> Path:
    if engine == "hybrid":
        return _render_hybrid(
            timeline_path,
            assets_path,
            out_path,
            project_dir=project_dir,
            composition_id=composition_id,
            theme_path=theme_path,
            min_free_gb=min_free_gb,
        )
    if engine == "ffmpeg":
        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
    if engine != "remotion":
        raise ValueError(f"Unsupported render engine: {engine}")
    project_dir = project_dir or (REPO_ROOT / "remotion")
    _validate_project_dir(project_dir)
    _regenerate_element_registries(project_dir, theme_path)
    out_path = out_path.resolve()
    _require_free_space(out_path.parent, min_free_gb)
    props_path = (out_path.parent / ".remotion-props.json").resolve()
    classified = _classify_assets(assets_path)
    _warn_cross_project_assets(classified)
    server_root = _server_root_for(assets_path, classified).resolve()
    try:
        port = _pick_free_port()
        handler = partial(_RangeHTTPRequestHandler, directory=str(server_root))
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise RuntimeError(f"Permission denied (1100): local HTTP asset server blocked: {exc}") from exc
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        resolved_registry = _resolve_assets(assets_path, server_root, port, classified)
        resolved_theme = theme_path or (WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json")
        theme_for_props = _resolved_theme_for_render(timeline_path, resolved_theme)
        # The timeline references a theme by slug + optional theme_overrides;
        # theme.visual.canvas is the source of truth for Remotion calculateMetadata.
        merged_props = {
            "timeline": _serialize_timeline(
                timeline_path,
                default_theme=str(theme_for_props.get("id") or "banodoco-default"),
            ),
            "assets": resolved_registry,
            "theme": theme_for_props,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        props_path.write_text(json.dumps(merged_props), encoding="utf-8")
        # Build the Remotion launch env from the canonical safe base plus the
        # Astrid runtime markers it propagates. We do NOT spread os.environ:
        # the only Node/Remotion additions are the safe-base PATH/HOME/TMPDIR
        # that npx + the headless renderer need, and any caller-provided
        # composition source override declared as a build-tool variable.
        remotion_env_additions: dict[str, str] = {}
        composition_src = (
            project_dir / "node_modules" / "@banodoco" / "timeline-composition" / "typescript" / "src"
        )
        if composition_src.is_dir():
            remotion_env_additions["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
        result = subprocess.run(
            [
                "npx",
                "remotion",
                "render",
                composition_id,
                "--props",
                str(props_path),
                "--output",
                str(out_path),
                "--allow-html-in-canvas",
            ],
            cwd=str(project_dir),
            env=build_child_subprocess_env(explicit_env=remotion_env_additions),
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            stderr_tail = _stderr_tail(result.stderr)
            message = f"Remotion render failed with exit code {result.returncode}"
            if stderr_tail:
                message = f"{message}\n{stderr_tail}"
            raise RuntimeError(message)
        props_path.unlink(missing_ok=True)
    finally:
        server.shutdown()
        server.server_close()
    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_remotion")
        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_remotion")
        render_id = audit.register_asset(
            kind="render",
            path=out_path,
            label="Rendered video",
            parents=[timeline_id, assets_id],
            stage="render_remotion",
            metadata={"composition": composition_id},
        )
        audit.register_node(
            stage="render_remotion",
            label="Render Remotion timeline",
            parents=[timeline_id, assets_id],
            outputs=[render_id],
            metadata={"composition": composition_id, "project_dir": str(project_dir)},
        )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--engine", choices=("remotion", "ffmpeg", "hybrid"), default="remotion")
    parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
    parser.add_argument("--composition", default="TimelineComposition")
    parser.add_argument("--min-free-gb", type=float, default=None, help="Abort before rendering unless this much free disk is available near --out.")
    parser.add_argument(
        "--theme",
        type=Path,
        default=REPO_ROOT / "themes" / "banodoco-default" / "theme.json",
    )
    args = parser.parse_args()
    try:
        output = render(
            args.timeline,
            args.assets,
            args.out,
            engine=args.engine,
            project_dir=args.project_dir,
            composition_id=args.composition,
            theme_path=args.theme,
            min_free_gb=args.min_free_gb,
        )
    except Exception as exc:  # pragma: no cover - CLI path
        print(str(exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
