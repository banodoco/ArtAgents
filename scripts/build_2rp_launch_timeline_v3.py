#!/usr/bin/env python3
"""Build a polished 2RP launch teaser with creator credit cards and bouncy transitions.

Sections: Intro, ART, LORAs, WORKFLOWS, AGENTS (coming soon), CTA.
Each content beat shows:
  - full-screen video clip
  - a credit card with the creator's Discord avatar + display name
  - the asset title
  - cross-fades between beats and a dedicated section title card between sections.
"""
import json
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "projects" / "2rp-launch-video"
PICKS = PROJECT / "2rp-assets" / "video-picks.json"
OUT = PROJECT / "launch-video"
OUT.mkdir(parents=True, exist_ok=True)
ASSET_DIR = OUT / "assets"
ASSET_DIR.mkdir(exist_ok=True)
AVATAR_DIR = ASSET_DIR / "avatars"
AVATAR_DIR.mkdir(exist_ok=True)

with PICKS.open() as f:
    picks = json.load(f)

WIDTH, HEIGHT, FPS = 1920, 1080, 30
DUR_INTRO = 2.5
DUR_SECTION = 1.5
DUR_ASSET = 2.0
DUR_CTA = 3.0
TRANSITION = 0.3

assets = {}
asset_index = 0


def _next_name(category):
    global asset_index
    name = f"{category}_{asset_index}"
    asset_index += 1
    return name


def _media_blob(item):
    return item.get("media") or item.get("cover") or item


def thumbnail_url(item):
    m = _media_blob(item)
    return (
        m.get("cloudflare_thumbnail_url")
        or m.get("backup_thumbnail_url")
        or m.get("thumbnailUrl")
        or item.get("cloudflare_thumbnail_url")
        or item.get("backup_thumbnail_url")
    )


def video_url(item):
    # Catalog may have already resolved a working URL (e.g., for validated workflows).
    if item.get("video_url"):
        return item["video_url"]
    m = _media_blob(item)
    return m.get("cloudflare_playback_hls_url") or m.get("hlsUrl") or item.get("cloudflare_playback_hls_url")


def title_of(item):
    return item.get("title") or item.get("name") or "Untitled"


def creator_of(item):
    return (
        item.get("creator_display_name")
        or item.get("creator_username")
        or item.get("creator")
        or ""
    )


def avatar_local(item):
    local = item.get("creator_avatar_local")
    if local:
        return OUT / local
    return None


def _register(path: Path, media_type: str) -> str:
    name = _next_name("asset")
    assets[name] = {"file": str(path.relative_to(OUT)), "type": media_type}
    return name


def _placeholder_avatar(display_name: str) -> Path:
    initials = "".join(w[:1] for w in display_name.split() if w)[:2].upper() or "?"
    path = AVATAR_DIR / f"placeholder_{initials}.png"
    if path.exists():
        return path
    img = Image.new("RGB", (256, 256), "#1a1a1a")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((256 - tw) / 2, (256 - th) / 2 - 10), initials, font=font, fill="#fde68a")
    img.save(path)
    return path


def _resolve_avatar(item) -> str:
    local = avatar_local(item)
    if local and local.exists():
        return _register(local, "image/png")
    placeholder = _placeholder_avatar(creator_of(item))
    return _register(placeholder, "image/png")


def _download_video_clip(item, category, duration=DUR_ASSET, start_offset=0.0):
    url = video_url(item)
    if not url:
        return None
    name = _next_name(category)
    local_path = ASSET_DIR / f"{name}.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", url,
        "-ss", str(start_offset), "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "23", "-preset", "veryfast",
        "-an",
        str(local_path),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=180, capture_output=True, text=True)
    except Exception as exc:
        print(f"WARN failed to clip {url}: {exc}")
        return None
    if not local_path.exists() or local_path.stat().st_size == 0:
        return None
    return _register(local_path, "video/mp4")


class TimelineBuilder:
    def __init__(self):
        self.clips = []
        self.t = 0.0

    def media(self, cid, at, duration, asset, transition=None, fade_in=0.0, fade_out=0.0,
              slide_in_x=0.0, slide_out_x=0.0, clip_type="media", params=None):
        clip = {
            "id": cid,
            "at": round(at, 3),
            "track": "media",
            "clipType": clip_type,
            "asset": asset,
            "hold": round(duration, 3),
            "volume": 0.0,
        }
        if params:
            clip["params"] = params
        if transition:
            clip["transition"] = transition
        if fade_in or fade_out or slide_in_x or slide_out_x:
            clip["effects"] = {}
            if fade_in:
                clip["effects"]["fade_in"] = fade_in
            if fade_out:
                clip["effects"]["fade_out"] = fade_out
            if slide_in_x:
                clip["effects"]["slide_in_x"] = slide_in_x
            if slide_out_x:
                clip["effects"]["slide_out_x"] = slide_out_x
        self.clips.append(clip)
        return self

    def text(self, cid, at, duration, content, font_size=72, color="#ffffff", y=540,
             align="center", bold=True, effects=None, track="title"):
        clip = {
            "id": cid,
            "at": round(at, 3),
            "track": track,
            "clipType": "text",
            "hold": round(duration, 3),
            "text": {
                "content": content,
                "fontSize": font_size,
                "color": color,
                "align": align,
                "bold": bold,
            },
            "x": 0,
            "y": y,
            "width": WIDTH,
            "height": 200,
        }
        if effects:
            clip["effects"] = effects
        self.clips.append(clip)
        return self

    def image(self, cid, at, duration, asset, x, y, w, h, fade_in=0.0, fade_out=0.0):
        clip = {
            "id": cid,
            "at": round(at, 3),
            "track": "credit",
            "clipType": "media",
            "asset": asset,
            "hold": round(duration, 3),
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "volume": 0.0,
        }
        if fade_in or fade_out:
            clip["effects"] = {}
            if fade_in:
                clip["effects"]["fade_in"] = fade_in
            if fade_out:
                clip["effects"]["fade_out"] = fade_out
        self.clips.append(clip)
        return self


def _intro(builder: TimelineBuilder):
    # Dark background image asset
    bg_path = ASSET_DIR / "intro_bg.png"
    Image.new("RGB", (WIDTH, HEIGHT), "#0b0b0f").save(bg_path)
    bg = _register(bg_path, "image/png")

    builder.media("intro_bg", 0, DUR_INTRO, bg, fade_in=0.3, fade_out=0.3)
    builder.text("intro_title", 0.1, DUR_INTRO - 0.2, "2RP", font_size=260,
                 color="#ffffff", y=360,
                 effects={"fade_in": 0.5, "fade_out": 0.3})
    builder.text("intro_sub", 0.5, DUR_INTRO - 0.6, "Second Renaissance People",
                 font_size=48, color="#fde68a", y=640,
                 effects={"fade_in": 0.4, "fade_out": 0.3})
    builder.t = DUR_INTRO


def _section_title(builder: TimelineBuilder, label: str):
    start = builder.t
    # Big centered section name that fades out slowly as the first asset rises in.
    builder.clips.append({
        "id": f"section_title_{label}",
        "at": round(start, 3),
        "track": "section",
        "clipType": "text",
        "hold": round(DUR_SECTION, 3),
        "text": {
            "content": label,
            "fontSize": 200,
            "color": "#ffffff",
            "align": "center",
            "bold": True,
        },
        "x": 0,
        "y": 380,
        "width": WIDTH,
        "height": 220,
        "effects": {"fade_in": 0.5, "fade_out": 0.8},
    })
    builder.t += DUR_SECTION


def _asset_beat(builder: TimelineBuilder, item, category: str, section_start: bool,
                has_prev: bool = False, has_next: bool = False):
    start = builder.t
    start_offset = float(item.get("clip_start_offset", 0.0))

    # Media starts with its labels. To give the cross-fade something to blend
    # into, the outgoing media stays on screen for TRANSITION seconds after its
    # labels leave (only when another clip follows).
    media_tail = TRANSITION if has_next else 0.0
    media_duration = DUR_ASSET + media_tail
    asset_name = _download_video_clip(item, category, duration=media_duration, start_offset=start_offset)

    # Cross-fade is stored on the *current* clip because the renderer groups
    # consecutive clips by inspecting the from-clip's transition field.
    transition = {"type": "cross-fade", "duration": TRANSITION} if has_next else None

    media_fx = {"fade_in": 0.2, "fade_out": 0.3, "slide_in_x": -350, "slide_out_x": 400}
    media_params = {}
    if has_prev:
        media_params["noFadeIn"] = True
    if has_next:
        media_params["noFadeOut"] = True
    if asset_name:
        builder.media(f"media_{asset_name}", start, media_duration, asset_name,
                      transition=transition,
                      fade_in=media_fx["fade_in"],
                      fade_out=media_fx["fade_out"],
                      slide_in_x=media_fx["slide_in_x"],
                      slide_out_x=media_fx["slide_out_x"],
                      clip_type="sliding-media",
                      params=media_params)
    else:
        # Fallback dark frame
        bg_path = ASSET_DIR / f"fallback_{asset_index}.png"
        Image.new("RGB", (WIDTH, HEIGHT), "#0b0b0f").save(bg_path)
        fb = _register(bg_path, "image/png")
        builder.media(f"media_fallback_{asset_index}", start, media_duration, fb,
                      transition=transition,
                      fade_in=media_fx["fade_in"],
                      fade_out=media_fx["fade_out"],
                      slide_in_x=media_fx["slide_in_x"],
                      slide_out_x=media_fx["slide_out_x"],
                      clip_type="sliding-media",
                      params=media_params)

    creator = creator_of(item)
    title = title_of(item)
    avatar_asset = _resolve_avatar(item)

    card_x, card_y = 80, 80
    avatar_size = 96
    card_w = 720
    card_h = avatar_size + 32

    slide_fx = {"fade_in": 0.2, "fade_out": 0.3, "slide_in_x": -350, "slide_out_x": 400}

    # Credit card (avatar + name + handle) slides in/out as one unit.
    builder.clips.append({
        "id": f"credit_{asset_index}",
        "at": round(start, 3),
        "track": "credit",
        "clipType": "text",
        "asset": avatar_asset,
        "hold": round(DUR_ASSET, 3),
        "x": card_x - 16,
        "y": card_y - 16,
        "width": card_w,
        "height": card_h,
        "text": {
            "content": creator,
            "fontSize": 32,
            "color": "#ffffff",
            "align": "left",
            "bold": True,
        },
        "params": {
            "subtitle": f"@{item.get('creator_username', creator).lower()}",
            "subtitlePosition": "below",
            "subtitleColor": "#fde68a",
            "subtitleFontSize": 22,
            "subtitleSpacing": 2,
            "subtitleTransform": "none",
            "background": "rgba(11, 11, 15, 0.9)",
            "borderRadius": 20,
            "border": "2px solid rgba(253, 230, 138, 0.47)",
            "padding": 16,
            "leftSpriteSize": avatar_size,
            "leftSpriteRadius": 12,
            "leftSpriteGap": 18,
        },
        "effects": slide_fx,
    })

    # Title at bottom
    builder.clips.append({
        "id": f"title_{asset_index}",
        "at": round(start, 3),
        "track": "title",
        "clipType": "text",
        "hold": round(DUR_ASSET, 3),
        "text": {
            "content": title,
            "fontSize": 44,
            "color": "#ffffff",
            "align": "left",
            "bold": True,
        },
        "x": 80,
        "y": HEIGHT - 130,
        "width": 900,
        "height": 90,
        "effects": slide_fx,
    })

    # Small category tag
    builder.clips.append({
        "id": f"tag_{asset_index}",
        "at": round(start, 3),
        "track": "title",
        "clipType": "text",
        "hold": round(DUR_ASSET, 3),
        "text": {
            "content": category.upper(),
            "fontSize": 22,
            "color": "#fde68a",
            "align": "left",
            "bold": True,
        },
        "x": 80,
        "y": HEIGHT - 168,
        "width": 200,
        "height": 40,
        "effects": slide_fx,
    })

    builder.t += DUR_ASSET


def _agents_section(builder: TimelineBuilder):
    _section_title(builder, "AGENTS")
    start = builder.t
    slide_fx = {"fade_in": 0.2, "fade_out": 0.3, "slide_in_x": -350, "slide_out_x": 400}
    for i in range(3):
        bg_path = ASSET_DIR / f"agent_bg_{i}.png"
        Image.new("RGB", (WIDTH, HEIGHT), "#0b0b0f").save(bg_path)
        bg = _register(bg_path, "image/png")
        has_next = i < 2
        media_duration = DUR_ASSET + (TRANSITION if has_next else 0.0)
        transition = {"type": "cross-fade", "duration": TRANSITION} if has_next else None
        media_params = {}
        if i > 0:
            media_params["noFadeIn"] = True
        if has_next:
            media_params["noFadeOut"] = True
        builder.media(f"agent_media_{i}", start + i * DUR_ASSET, media_duration, bg,
                      transition=transition,
                      fade_in=slide_fx["fade_in"],
                      fade_out=slide_fx["fade_out"],
                      slide_in_x=slide_fx["slide_in_x"],
                      slide_out_x=slide_fx["slide_out_x"],
                      clip_type="sliding-media",
                      params=media_params)
        builder.text(f"agent_{i}", start + i * DUR_ASSET, DUR_ASSET,
                     "AGENTS" if i == 0 else "Tools that create with you",
                     font_size=100 if i == 0 else 48,
                     color="#ffffff" if i == 0 else "#fde68a",
                     y=460 if i == 0 else 560,
                     track="title",
                     effects=slide_fx)
    builder.t = start + 3 * DUR_ASSET


def _cta(builder: TimelineBuilder):
    start = builder.t
    bg_path = ASSET_DIR / "cta_bg.png"
    Image.new("RGB", (WIDTH, HEIGHT), "#0b0b0f").save(bg_path)
    bg = _register(bg_path, "image/png")
    builder.media("cta_bg", start, DUR_CTA, bg, fade_in=0.3, fade_out=0.5)
    builder.text("cta_title", start + 0.2, DUR_CTA - 0.4, "banodoco.ai/2rp",
                 font_size=120, color="#fde68a", y=440,
                 effects={"fade_in": 0.6, "fade_out": 0.4})
    builder.text("cta_sub", start + 0.6, DUR_CTA - 0.8,
                 "Art · LoRAs · Workflows · Agents",
                 font_size=48, color="#ffffff", y=600,
                 effects={"fade_in": 0.5, "fade_out": 0.4})
    builder.t = start + DUR_CTA


def main():
    builder = TimelineBuilder()
    _intro(builder)

    sections = [
        ("ART", "Art", picks.get("art", [])),
        ("LORAs", "LoRAs", picks.get("loras", [])),
        ("WORKFLOWS", "Workflows", picks.get("workflows", [])),
    ]

    for label, category, items in sections:
        _section_title(builder, label)
        section_items = items[:3]
        # Every section asset starts its media TRANSITION seconds before its
        # labels so consecutive media clips overlap and the cross-fade has
        # something to blend into instead of fading to black.
        for idx, item in enumerate(section_items):
            _asset_beat(
                builder, item, category, section_start=(idx == 0),
                has_prev=(idx > 0),
                has_next=(idx < len(section_items) - 1),
            )

    _agents_section(builder)
    _cta(builder)

    # Track order is reversed at render time, so list bottom-to-top here:
    # media -> section card -> title overlay -> credit card overlay.
    tracks = [
        {"id": "credit", "kind": "visual", "label": "Credit"},
        {"id": "title", "kind": "visual", "label": "Title"},
        {"id": "section", "kind": "visual", "label": "Section"},
        {"id": "media", "kind": "visual", "label": "Media"},
    ]

    timeline = {
        "theme": "2rp",
        "tracks": tracks,
        "clips": builder.clips,
    }

    with (OUT / "hype.timeline.json").open("w") as f:
        json.dump(timeline, f, indent=2)

    with (OUT / "hype.assets.json").open("w") as f:
        json.dump({"assets": assets}, f, indent=2)

    with (OUT / "example-manifest.json").open("w") as f:
        json.dump({"duration_seconds": builder.t, "asset_count": len(assets)}, f, indent=2)

    print(f"Wrote {OUT / 'hype.timeline.json'}")
    print(f"Wrote {OUT / 'hype.assets.json'}")
    print(f"Total duration: {builder.t:.1f}s, assets: {len(assets)}")


if __name__ == "__main__":
    main()
