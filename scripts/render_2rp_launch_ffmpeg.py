#!/usr/bin/env python3
"""Render the 2RP launch teaser with ffmpeg (PIL frames + ffmpeg encode)."""
import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
TIMELINE = ROOT / "projects" / "2rp-launch-video" / "launch-video" / "hype.timeline.json"
ASSETS = ROOT / "projects" / "2rp-launch-video" / "launch-video" / "hype.assets.json"
OUT = ROOT / "projects" / "2rp-launch-video" / "renders" / "2rp-launch.mp4"
OUT.parent.mkdir(parents=True, exist_ok=True)

with TIMELINE.open() as f:
    timeline = json.load(f)
with ASSETS.open() as f:
    registry = json.load(f)

canvas = timeline["theme_overrides"]["visual"]["canvas"]
W, H, FPS = canvas["width"], canvas["height"], canvas["fps"]

# Resolve asset files relative to timeline dir.
asset_dir = TIMELINE.parent
asset_files = {}
for name, entry in registry.get("assets", {}).items():
    if "file" in entry:
        asset_files[name] = asset_dir / entry["file"]
    elif "url" in entry:
        asset_files[name] = entry["url"]

# Try to load fonts.
def get_font(size):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_title = get_font(180)
font_cat = get_font(130)
font_caption = get_font(38)
font_cta = get_font(90)

# Sort clips by time.
clips = sorted(timeline["clips"], key=lambda c: c["at"])

# Determine total duration.
max_end = 0.0
for c in clips:
    end = c["at"] + c.get("hold", 0)
    max_end = max(max_end, end)
total_frames = int(max_end * FPS)

# Build a frame lookup: for each frame, which text/media clips are active.
def active_clips_at(t):
    out = []
    for c in clips:
        start = c["at"]
        dur = c.get("hold", 0)
        if start <= t < start + dur:
            out.append(c)
    return out


def draw_text_centered(draw, text, y, font, fill, max_width=None):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    if max_width and tw > max_width:
        # Simple truncate
        while tw > max_width and len(text) > 3:
            text = text[:-4] + "..."
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)


def render_frame(frame_idx):
    t = frame_idx / FPS
    img = Image.new("RGB", (W, H), "#0b0b0f")
    draw = ImageDraw.Draw(img)
    active = active_clips_at(t)

    # Draw media first (only one expected per track)
    media_clips = [c for c in active if c["clipType"] == "media"]
    text_clips = [c for c in active if c["clipType"] == "text"]

    for c in media_clips:
        asset = c.get("asset")
        path = asset_files.get(asset)
        if path and isinstance(path, Path) and path.exists():
            try:
                thumb = Image.open(path).convert("RGB")
                # Cover-fit to canvas
                thumb_ratio = thumb.width / thumb.height
                canvas_ratio = W / H
                if thumb_ratio > canvas_ratio:
                    new_h = H
                    new_w = int(new_h * thumb_ratio)
                else:
                    new_w = W
                    new_h = int(new_w / thumb_ratio)
                thumb = thumb.resize((new_w, new_h), Image.LANCZOS)
                x = (W - new_w) // 2
                y = (H - new_h) // 2
                img.paste(thumb, (x, y))
                # dark vignette for text readability
                overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ov_draw = ImageDraw.Draw(overlay)
                ov_draw.rectangle([0, 0, W, H], fill=(0, 0, 0, 120))
                img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
                draw = ImageDraw.Draw(img)
            except Exception as exc:
                print(f"WARN media error {asset}: {exc}")

    # Draw text clips
    for c in text_clips:
        text_cfg = c.get("text", {})
        content = text_cfg.get("content", "")
        color = text_cfg.get("color", "#ffffff")
        size = text_cfg.get("fontSize", 64)
        params = c.get("params", {})
        anchor = params.get("anchor", "center")
        offset_y = params.get("offsetY", 0)

        # Pick font by size
        if size >= 140:
            font = font_title if size >= 180 else font_cat
        elif size >= 70:
            font = font_cta
        else:
            font = font_caption

        if anchor == "center":
            bbox = draw.textbbox((0, 0), content, font=font)
            th = bbox[3] - bbox[1]
            y = (H - th) // 2 + offset_y
            draw_text_centered(draw, content, y, font, color)
        elif anchor == "bottom":
            y = H - 120 + offset_y
            draw_text_centered(draw, content, y, font, color, max_width=W - 200)
        else:
            draw_text_centered(draw, content, H // 2 + offset_y, font, color)

    return img


# Render frames to temp dir and encode with ffmpeg.
with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    print(f"Rendering {total_frames} frames to {tmp_path} ...")
    for i in range(total_frames):
        frame = render_frame(i)
        frame.save(tmp_path / f"frame_{i:06d}.png")
        if i % 30 == 0:
            print(f"  frame {i}/{total_frames}")

    cmd = [
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", str(tmp_path / "frame_%06d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "23", "-preset", "fast",
        str(OUT),
    ]
    print(f"Encoding {OUT} ...")
    subprocess.run(cmd, check=True)

print(f"Done: {OUT}")
