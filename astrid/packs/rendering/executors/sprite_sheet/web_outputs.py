"""ffmpeg and web output helpers for sprite sheet processing."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from astrid.packs.generation.executors.generate_image_openai.run import _die

from .png_io import _alpha_bbox, _png_dimensions, _read_rgba_png, scrub_fully_transparent_rgb
from .sheet import _hex_color_no_hash


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def remove_chroma_key(
    input_path: Path,
    output_path: Path,
    *,
    key_color: str,
    similarity: float,
    blend: float,
    force: bool,
) -> None:
    if output_path.exists() and not force:
        _die(f"Output exists: {output_path} (use --force to overwrite)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    color = "0x" + _hex_color_no_hash(key_color)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-i",
            str(input_path),
            "-vf",
            f"format=rgba,colorkey={color}:{similarity}:{blend}",
            "-frames:v",
            "1",
            str(output_path),
        ]
    )


def slice_frames(
    sheet_path: Path,
    frames_dir: Path,
    *,
    cols: int,
    rows: int,
    frame_width: int,
    frame_height: int,
    frame_count: int,
    trim: int,
    force: bool,
) -> list[str]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    output_width = frame_width - trim * 2
    output_height = frame_height - trim * 2
    if output_width < 16 or output_height < 16:
        _die("--slice-trim is too large for the frame size")
    for index in range(frame_count):
        col = index % cols
        row = index // cols
        x = col * frame_width + trim
        y = row * frame_height + trim
        out = frames_dir / f"frame_{index + 1:03d}.png"
        if out.exists() and not force:
            _die(f"Output exists: {out} (use --force to overwrite)")
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y" if force else "-n",
                "-i",
                str(sheet_path),
                "-vf",
                f"crop={output_width}:{output_height}:{x}:{y}",
                "-frames:v",
                "1",
                str(out),
            ]
        )
        outputs.append(str(out))
    return outputs


def assemble_review_video(
    frames_dir: Path, video_path: Path, *, fps: int, background: str, force: bool
) -> None:
    if video_path.exists() and not force:
        _die(f"Output exists: {video_path} (use --force to overwrite)")
    video_path.parent.mkdir(parents=True, exist_ok=True)
    frame_width, frame_height = _png_dimensions(frames_dir / "frame_001.png")
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%03d.png"),
            "-f",
            "lavfi",
            "-i",
            f"color=c={background}:s={frame_width}x{frame_height}:r={fps}",
            "-filter_complex",
            "[1:v][0:v]overlay=shortest=1:format=auto,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "15",
            "-preset",
            "slow",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
    )


def assemble_prores_video(frames_dir: Path, video_path: Path, *, fps: int, force: bool) -> None:
    if video_path.exists() and not force:
        _die(f"Output exists: {video_path} (use --force to overwrite)")
    video_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%03d.png"),
            "-c:v",
            "prores_ks",
            "-profile:v",
            "4",
            "-pix_fmt",
            "yuva444p10le",
            str(video_path),
        ]
    )


def _scale_filter_for_web(max_dim: int | None) -> str:
    if max_dim is None or max_dim <= 0:
        return "format=rgba"
    return (
        "scale='if(gt(iw,ih),min(iw,"
        f"{max_dim}),-2)':'if(gt(ih,iw),min(ih,{max_dim}),-2)':force_original_aspect_ratio=decrease,"
        "format=rgba"
    )


def convert_image_to_webp(
    input_path: Path,
    output_path: Path,
    *,
    quality: int,
    lossless: bool,
    max_dim: int | None,
    force: bool,
) -> None:
    if output_path.exists() and not force:
        _die(f"Output exists: {output_path} (use --force to overwrite)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-i",
            str(input_path),
            "-vf",
            _scale_filter_for_web(max_dim),
            "-frames:v",
            "1",
            "-c:v",
            "libwebp",
            "-lossless",
            "1" if lossless else "0",
            "-quality",
            str(quality),
            str(output_path),
        ]
    )


def convert_frames_to_webp(
    frames: list[str],
    out_dir: Path,
    *,
    quality: int,
    lossless: bool,
    max_dim: int | None,
    force: bool,
) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for index, frame in enumerate(frames, start=1):
        out = out_dir / f"frame_{index:03d}.webp"
        convert_image_to_webp(
            Path(frame), out, quality=quality, lossless=lossless, max_dim=max_dim, force=force
        )
        outputs.append(str(out))
    return outputs


def assemble_web_mp4(
    frames_dir: Path,
    video_path: Path,
    *,
    fps: int,
    background: str,
    max_dim: int | None,
    crf: int,
    force: bool,
) -> None:
    if video_path.exists() and not force:
        _die(f"Output exists: {video_path} (use --force to overwrite)")
    video_path.parent.mkdir(parents=True, exist_ok=True)
    frame_width, frame_height = _png_dimensions(frames_dir / "frame_001.png")
    scale_filter = ""
    if max_dim is not None and max_dim > 0:
        scale_filter = f",scale='if(gt(iw,ih),min(iw,{max_dim}),-2)':'if(gt(ih,iw),min(ih,{max_dim}),-2)':force_original_aspect_ratio=decrease"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%03d.png"),
            "-f",
            "lavfi",
            "-i",
            f"color=c={background}:s={frame_width}x{frame_height}:r={fps}",
            "-filter_complex",
            f"[1:v][0:v]overlay=shortest=1:format=auto{scale_filter},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            "medium",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
    )


def assemble_animated_webp(
    frames_dir: Path, output_path: Path, *, fps: int, quality: int, max_dim: int | None, force: bool
) -> None:
    if output_path.exists() and not force:
        _die(f"Output exists: {output_path} (use --force to overwrite)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_chain = _scale_filter_for_web(max_dim)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%03d.png"),
            "-vf",
            filter_chain,
            "-loop",
            "0",
            "-c:v",
            "libwebp_anim",
            "-lossless",
            "0",
            "-quality",
            str(quality),
            "-compression_level",
            "6",
            str(output_path),
        ]
    )


def assemble_sprite_sheet_from_frames(
    frames_dir: Path, output_path: Path, *, cols: int, rows: int, force: bool
) -> None:
    if output_path.exists() and not force:
        _die(f"Output exists: {output_path} (use --force to overwrite)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-i",
            str(frames_dir / "frame_%03d.png"),
            "-filter_complex",
            f"tile={cols}x{rows}:padding=0:margin=0:color=0x00000000,format=rgba",
            "-frames:v",
            "1",
            str(output_path),
        ]
    )
    scrub_fully_transparent_rgb(output_path)


def build_web_outputs(
    *,
    source_sheet: Path,
    frames: list[str],
    frames_dir: Path,
    out_dir: Path,
    fps: int,
    background: str,
    quality: int,
    lossless_frames: bool,
    max_dim: int | None,
    mp4_crf: int,
    animated: bool,
    force: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_width: int | None = None
    frame_height: int | None = None
    if frames:
        frame_width, frame_height = _png_dimensions(Path(frames[0]))
    sheet_webp = out_dir / "sprite_sheet.webp"
    frames_web_dir = out_dir / "frames"
    mp4_path = out_dir / "sprite_preview_web.mp4"
    animated_webp = out_dir / "sprite_preview.webp"
    convert_image_to_webp(
        source_sheet,
        sheet_webp,
        quality=quality,
        lossless=lossless_frames,
        max_dim=None,
        force=force,
    )
    frame_outputs = convert_frames_to_webp(
        frames,
        frames_web_dir,
        quality=quality,
        lossless=lossless_frames,
        max_dim=max_dim,
        force=force,
    )
    assemble_web_mp4(
        frames_dir,
        mp4_path,
        fps=fps,
        background=background,
        max_dim=max_dim,
        crf=mp4_crf,
        force=force,
    )
    animated_webp_path: str | None = None
    if animated:
        try:
            assemble_animated_webp(
                frames_dir, animated_webp, fps=fps, quality=quality, max_dim=max_dim, force=force
            )
            animated_webp_path = str(animated_webp)
        except Exception as exc:  # noqa: BLE001 - optional animated preview must not block export
            print(
                f"Warning: animated WebP export failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
    web_manifest = {
        "sheet_webp": str(sheet_webp),
        "frames_webp": frame_outputs,
        "review_mp4": str(mp4_path),
        "animated_webp": animated_webp_path,
        "quality": quality,
        "lossless_frames": lossless_frames,
        "max_dim": max_dim,
        "mp4_crf": mp4_crf,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "frame_count": len(frames),
        "recommended_runtime": "Use sheet_webp as a CSS/canvas atlas when frame dimensions match runtime needs; use frames_webp for lazy-loaded frame sequences.",
    }
    (out_dir / "sprite_web_manifest.json").write_text(
        json.dumps(web_manifest, indent=2) + "\n", encoding="utf-8"
    )
    return web_manifest


def normalize_frame_frame(
    path: Path, out_path: Path, *, margin: int, force: bool
) -> dict[str, Any]:
    width, height, pixels = _read_rgba_png(path)
    bbox = _alpha_bbox(pixels, width, height)
    if bbox is None:
        if path != out_path:
            out_path.write_bytes(path.read_bytes())
        return {"path": str(out_path), "empty": True, "scaled": False}
    min_x, min_y, max_x, max_y = bbox
    crop_w = max_x - min_x + 1
    crop_h = max_y - min_y + 1
    target_w = max(1, width - margin * 2)
    target_h = max(1, height - margin * 2)
    scale = min(1.0, target_w / crop_w, target_h / crop_h)
    crop_expr = f"crop={crop_w}:{crop_h}:{min_x}:{min_y}"
    if scale < 0.999:
        scaled_w = max(1, int(round(crop_w * scale)))
        scaled_h = max(1, int(round(crop_h * scale)))
        filter_chain = f"{crop_expr},scale={scaled_w}:{scaled_h}:flags=lanczos,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    else:
        filter_chain = f"{crop_expr},pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    if out_path.exists() and not force:
        from astrid.packs.generation.executors.generate_image_openai.run import _die

        _die(f"Output exists: {out_path} (use --force to overwrite)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if force else "-n",
            "-i",
            str(path),
            "-vf",
            filter_chain,
            "-frames:v",
            "1",
            str(out_path),
        ]
    )
    scrub_fully_transparent_rgb(out_path)
    return {
        "path": str(out_path),
        "empty": False,
        "scaled": scale < 0.999,
        "scale": scale,
        "source_bbox": [min_x, min_y, max_x, max_y],
    }


def normalize_frames(
    frames: list[str], out_dir: Path, *, margin: int, force: bool
) -> tuple[list[str], list[dict[str, Any]]]:
    normalized: list[str] = []
    report: list[dict[str, Any]] = []
    for index, frame in enumerate(frames, start=1):
        out = out_dir / f"frame_{index:03d}.png"
        item = normalize_frame_frame(Path(frame), out, margin=margin, force=force)
        normalized.append(str(out))
        report.append(item)
    return normalized, report
