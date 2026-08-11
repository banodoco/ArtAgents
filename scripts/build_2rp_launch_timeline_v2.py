#!/usr/bin/env python3
"""Build a sexy 2RP launch teaser using the proper Astrid timeline format.

Sections: Intro, ART, LORAs, WORKFLOWS, AGENTS (coming soon), CTA.
Each content example shows the creator/artist name at the top and the title below.

- Theme: "2rp" (custom Astrid theme matching the live /2rp page style)
- Art & LoRA & Workflow examples: short MP4 clips downloaded from Cloudflare HLS streams
- Agents: placeholder dark frames
- Transitions between clips
- Entrance/exit animations on text
"""
import json
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "projects" / "2rp-launch-video"
PICKS = PROJECT / "2rp-assets" / "video-picks.json"
OUT = PROJECT / "launch-video"
OUT.mkdir(parents=True, exist_ok=True)
ASSET_DIR = OUT / "assets"
ASSET_DIR.mkdir(exist_ok=True)

with PICKS.open() as f:
    picks = json.load(f)


def _media_blob(item):
    return item.get("media") or item.get("cover") or item


def thumbnail_url(item):
    m = _media_blob(item)
    return m.get("cloudflare_thumbnail_url") or m.get("backup_thumbnail_url") or m.get("thumbnailUrl") or item.get("cloudflare_thumbnail_url") or item.get("backup_thumbnail_url")


def video_url(item):
    m = _media_blob(item)
    return m.get("cloudflare_playback_hls_url") or m.get("hlsUrl") or item.get("cloudflare_playback_hls_url")


def title_of(item):
    return item.get("title") or item.get("name") or "Untitled"


def creator_of(item):
    return item.get("creator") or item.get("creator_display_name") or item.get("creator_username") or item.get("author") or ""


assets = {}
asset_index = 0
example_slots = []


def _next_name(category):
    global asset_index
    name = f"{category}_{asset_index}"
    asset_index += 1
    return name


def download_thumb(item, category):
    url = thumbnail_url(item)
    if not url:
        return None
    name = _next_name(category)
    ext = Path(url.split("?")[0]).suffix or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    local_path = ASSET_DIR / f"{name}{ext}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, local_path.open("wb") as f:
            f.write(resp.read())
    except Exception as exc:
        print(f"WARN failed to download {url}: {exc}")
        return None
    assets[name] = {
        "file": str(local_path.relative_to(OUT)),
        "type": "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png",
    }
    return name


def clip_video(item, category, duration_seconds=1.5):
    """Download a short clip from the HLS video URL."""
    url = video_url(item)
    if not url:
        return None
    name = _next_name(category)
    local_path = ASSET_DIR / f"{name}.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", url,
        "-ss", "0", "-t", str(duration_seconds),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "23", "-preset", "veryfast",
        "-an",
        str(local_path),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=180, capture_output=True, text=True)
    except Exception as exc:
        print(f"WARN failed to clip video {url}: {exc}")
        return None
    if not local_path.exists() or local_path.stat().st_size == 0:
        print(f"WARN empty clip for {url}")
        return None
    assets[name] = {
        "file": str(local_path.relative_to(OUT)),
        "type": "video/mp4",
    }
    return name


def add_examples(category_key, display_name, items):
    for item in items[:3]:
        asset_name = clip_video(item, category_key, duration_seconds=1.5)
        if asset_name is None:
            asset_name = download_thumb(item, category_key)
        example_slots.append({
            "category": display_name,
            "category_key": category_key,
            "title": title_of(item),
            "creator": creator_of(item),
            "asset": asset_name,
            "thumb_url": thumbnail_url(item),
            "video_url": video_url(item),
        })


# Build example slots in the order they will appear.
add_examples("art", "ART", picks.get("art", []))
add_examples("loras", "LORAs", picks.get("loras", []))
add_examples("workflows", "WORKFLOWS", picks.get("workflows", []))

# Agents: no approved nodes yet; use text placeholders.
for i in range(3):
    example_slots.append({
        "category": "AGENTS",
        "category_key": "agents",
        "title": "Coming soon",
        "creator": "",
        "asset": None,
        "thumb_url": None,
        "video_url": None,
    })

# Timeline construction.
WIDTH, HEIGHT, FPS = 1920, 1080, 30
DUR_INTRO = 2.0
DUR_CATEGORY = 1.5
DUR_EXAMPLE = 1.5
DUR_CTA = 3.0

tracks = [
    {"id": "media", "kind": "visual", "label": "Media"},
    {"id": "text", "kind": "visual", "label": "Text"},
]

clips = []


def text_clip(cid, at, duration, content, font_size=72, color="#ffffff", track="text", y=540, opacity=1.0, entrance=None, exit_=None):
    clip = {
        "id": cid,
        "at": at,
        "track": track,
        "clipType": "text",
        "hold": duration,
        "text": {
            "content": content,
            "fontSize": font_size,
            "color": color,
            "align": "center",
            "bold": True,
        },
        "x": 0,
        "y": y,
        "width": WIDTH,
        "height": 200,
    }
    if opacity < 1.0:
        clip["opacity"] = opacity
    if entrance:
        clip["entrance"] = entrance
    if exit_:
        clip["exit"] = exit_
    return clip


def media_clip(cid, at, duration, asset, transition=None):
    clip = {
        "id": cid,
        "at": at,
        "track": "media",
        "clipType": "media",
        "asset": asset,
        "hold": duration,
        "volume": 0.0,
    }
    if transition:
        clip["transition"] = transition
    return clip


# Intro: 2RP
clips.append(media_clip("intro_bg", 0, DUR_INTRO, None))
clips.append(text_clip("intro_title", 0, DUR_INTRO, "2RP", font_size=240, y=420,
                       entrance={"type": "fade-up", "duration": 0.4},
                       exit_={"type": "fade", "duration": 0.3}))
clips.append(text_clip("intro_sub", 0.3, DUR_INTRO - 0.3, "2nd Renaissance People", font_size=42, color="#fde68a", y=620,
                       entrance={"type": "fade-up", "duration": 0.4},
                       exit_={"type": "fade", "duration": 0.3}))

t = DUR_INTRO

sections = [
    ("ART", "art"),
    ("LORAs", "loras"),
    ("WORKFLOWS", "workflows"),
    ("AGENTS", "agents"),
]

for section_title, section_key in sections:
    # Category title card
    clips.append(text_clip(f"cat_{section_key}", t, DUR_CATEGORY, section_title, font_size=180, y=460,
                           entrance={"type": "scale-in", "duration": 0.5},
                           exit_={"type": "fade", "duration": 0.3}))
    t += DUR_CATEGORY

    # Examples
    section_examples = [s for s in example_slots if s["category"] == section_title]
    for idx, ex in enumerate(section_examples[:3]):
        cid_base = f"ex_{section_key}_{idx}"
        tr = {"type": "cross-fade", "duration": 0.25}

        if ex["asset"]:
            clips.append(media_clip(f"{cid_base}_media", t, DUR_EXAMPLE, ex["asset"], transition=tr))
            if assets.get(ex["asset"], {}).get("type", "").startswith("image"):
                clips[-1]["entrance"] = {"type": "scale-in", "duration": DUR_EXAMPLE}
        else:
            clips.append(text_clip(f"{cid_base}_bg", t, DUR_EXAMPLE, "·", font_size=1, color="#0b0b0f", y=540, track="media"))

        # Creator / artist name at the top
        if ex["creator"]:
            clips.append(text_clip(f"{cid_base}_creator", t + 0.05, DUR_EXAMPLE - 0.1, ex["creator"], font_size=34, color="#fde68a", y=80,
                                   entrance={"type": "fade-up", "duration": 0.25},
                                   exit_={"type": "fade", "duration": 0.2}))

        # Title at the bottom
        clips.append(text_clip(f"{cid_base}_title", t + 0.1, DUR_EXAMPLE - 0.2, ex["title"], font_size=40, color="#ffffff", y=HEIGHT - 120,
                               entrance={"type": "slide-left", "duration": 0.3},
                               exit_={"type": "fade", "duration": 0.25}))
        t += DUR_EXAMPLE

# Outro CTA
clips.append(text_clip("cta_title", t, DUR_CTA, "banodoco.ai/2rp", font_size=120, color="#fde68a", y=460,
                       entrance={"type": "fade-up", "duration": 0.6},
                       exit_={"type": "fade", "duration": 0.5}))
clips.append(text_clip("cta_sub", t + 0.5, DUR_CTA - 0.5, "Art · LoRAs · Workflows · Agents", font_size=48, y=600,
                       entrance={"type": "fade-up", "duration": 0.5},
                       exit_={"type": "fade", "duration": 0.4}))

# Replace intro placeholder with a dark frame.
intro_bg_path = ASSET_DIR / "intro_bg.png"
Image.new("RGB", (WIDTH, HEIGHT), "#0b0b0f").save(intro_bg_path)
assets["intro_bg"] = {"file": str(intro_bg_path.relative_to(OUT)), "type": "image/png"}
for c in clips:
    if c["id"] == "intro_bg":
        c["asset"] = "intro_bg"

# Agent placeholders: dark frames.
for i in range(3):
    p = ASSET_DIR / f"agent_bg_{i}.png"
    Image.new("RGB", (WIDTH, HEIGHT), "#0b0b0f").save(p)
    name = f"agent_{i}"
    assets[name] = {"file": str(p.relative_to(OUT)), "type": "image/png"}
    for c in clips:
        if c["id"].startswith(f"ex_agents_{i}") and c.get("clipType") == "media":
            c["asset"] = name
            c["entrance"] = {"type": "scale-in", "duration": DUR_EXAMPLE}

# Remove any accidental placeholder media clips without assets.
clips = [c for c in clips if not (c.get("clipType") == "media" and c.get("asset") is None)]

timeline = {
    "theme": "2rp",
    "tracks": tracks,
    "clips": clips,
}

assets_registry = {"assets": assets}

with (OUT / "hype.timeline.json").open("w") as f:
    json.dump(timeline, f, indent=2)

with (OUT / "hype.assets.json").open("w") as f:
    json.dump(assets_registry, f, indent=2)

with (OUT / "example-manifest.json").open("w") as f:
    json.dump({"examples": example_slots, "duration_seconds": t + DUR_CTA}, f, indent=2)

print(f"Wrote {OUT / 'hype.timeline.json'}")
print(f"Wrote {OUT / 'hype.assets.json'}")
print(f"Total duration: {t + DUR_CTA:.1f}s, assets: {len(assets)}")
