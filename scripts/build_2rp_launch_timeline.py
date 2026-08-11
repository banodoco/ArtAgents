#!/usr/bin/env python3
"""Build a fast ~20s Astrid launch teaser for https://banodoco.ai/2rp.

This version uses actual video clips for art examples (sourced from the
Cloudflare HLS streams listed in catalog.json) and thumbnails for the other
categories.
"""
import json
import subprocess
import urllib.request
from pathlib import Path

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


def clip_video(item, category, duration_seconds=1.0):
    """Download a short clip from the HLS video URL for the art examples."""
    url = video_url(item)
    if not url:
        return None
    name = _next_name(category)
    local_path = ASSET_DIR / f"{name}.mp4"
    # Cloudflare Stream HLS manifests are stable; trim the first N seconds.
    # Seeking after -i is more reliable for HLS than fast-seek before input.
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
        subprocess.run(cmd, check=True, timeout=120)
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


# Art: use short video clips.
for item in picks.get("art", [])[:3]:
    asset_name = clip_video(item, "art", duration_seconds=1.0)
    if asset_name is None:
        asset_name = download_thumb(item, "art")
    example_slots.append({
        "category": "ART",
        "title": title_of(item),
        "asset": asset_name,
        "thumb_url": thumbnail_url(item),
        "video_url": video_url(item),
    })

# Resources: thumbnails (LoRAs/workflows are not videos).
for item in picks.get("resources", [])[:3]:
    asset_name = download_thumb(item, "resources")
    example_slots.append({
        "category": "RESOURCES",
        "title": title_of(item),
        "asset": asset_name,
        "thumb_url": thumbnail_url(item),
        "video_url": None,
    })

# Posts: use community-news images since real posts have no cover media.
for item in picks.get("community_news", [])[:3]:
    media_urls = item.get("mediaUrls", [])
    image_items = [m for m in media_urls if m.get("type") == "image"]
    pseudo = {"cloudflare_thumbnail_url": image_items[0]["url"]} if image_items else {}
    name = download_thumb(pseudo, "posts")
    example_slots.append({
        "category": "POSTS",
        "title": item.get("title", "Community update"),
        "asset": name,
        "thumb_url": image_items[0]["url"] if image_items else None,
        "video_url": None,
    })

# Agents: no approved nodes yet; use text placeholders.
for i in range(3):
    example_slots.append({
        "category": "AGENTS",
        "title": "Coming soon",
        "asset": None,
        "thumb_url": None,
        "video_url": None,
    })

# Timeline construction: ~20 seconds, 1920x1080 @ 30fps.
WIDTH, HEIGHT, FPS = 1920, 1080, 30
DUR_INTRO = 1.5
DUR_CATEGORY = 1.5
DUR_EXAMPLE = 1.0
DUR_CTA = 2.0

tracks = [
    {"id": "media", "kind": "visual", "label": "Media"},
    {"id": "titles", "kind": "visual", "label": "Titles"},
    {"id": "captions", "kind": "visual", "label": "Captions"},
]

clips = []


def text_clip(cid, at, duration, text, track, font_size=96, color="#ffffff", align="center", bold=True, anchor="center", offset_y=0, opacity=1.0):
    params = {"anchor": anchor, "offsetY": offset_y}
    if opacity < 1.0:
        params["opacity"] = opacity
    return {
        "id": cid,
        "at": at,
        "track": track,
        "clipType": "text",
        "hold": duration,
        "text": {
            "content": text,
            "fontSize": font_size,
            "color": color,
            "align": align,
            "bold": bold,
        },
        "params": params,
    }


def media_clip(cid, at, duration, asset, volume=0.0):
    return {
        "id": cid,
        "at": at,
        "track": "media",
        "clipType": "media",
        "asset": asset,
        "hold": duration,
        "volume": volume,
    }


# Intro: 2RP
t = 0.0
clips.append(text_clip("intro_2rp", t, DUR_INTRO, "2RP", "titles", font_size=220, anchor="center"))
clips.append(text_clip("intro_tag", t + 0.4, DUR_INTRO - 0.4, "2nd Renaissance People", "captions", font_size=36, color="#fde68a", anchor="center", offset_y=160))
t += DUR_INTRO

# Four categories
sections = [
    ("ART", "art"),
    ("RESOURCES", "resources"),
    ("POSTS", "posts"),
    ("AGENTS", "agents"),
]

for section_title, section_key in sections:
    clips.append(text_clip(f"cat_{section_key}", t, DUR_CATEGORY, section_title, "titles", font_size=160, anchor="center"))
    t += DUR_CATEGORY

    # Examples
    section_examples = [s for s in example_slots if s["category"] == section_title]
    for idx, ex in enumerate(section_examples[:3]):
        cid_base = f"ex_{section_key}_{idx}"
        if ex["asset"]:
            clips.append(media_clip(f"{cid_base}_media", t, DUR_EXAMPLE, ex["asset"]))
        else:
            # placeholder colored background via text with no asset
            clips.append(text_clip(f"{cid_base}_bg", t, DUR_EXAMPLE, "·", "media", font_size=1, color="#0b0b0f", anchor="center"))
        # caption at bottom
        clips.append(text_clip(f"{cid_base}_title", t + 0.1, DUR_EXAMPLE - 0.1, ex["title"], "captions", font_size=32, color="#fde68a", anchor="bottom", offset_y=-80))
        t += DUR_EXAMPLE

# Outro CTA
clips.append(text_clip("cta_line1", t, DUR_CTA, "Go to", "titles", font_size=80, anchor="center", offset_y=-60))
clips.append(text_clip("cta_line2", t + 0.5, DUR_CTA - 0.5, "banodoco.ai/2rp", "titles", font_size=96, color="#fde68a", anchor="center", offset_y=60))

timeline = {
    "theme": "banodoco-default",
    "theme_overrides": {
        "visual": {
            "color": {
                "fg": "#ffffff",
                "bg": "#0b0b0f",
                "accent": "#fde68a",
            },
            "type": {
                "families": {
                    "heading": "Inter, system-ui, sans-serif",
                    "body": "Inter, system-ui, sans-serif",
                },
                "size": {"base": 48, "small": 28, "large": 128},
                "weight": {"normal": 400, "bold": 800},
                "lineHeight": 1.05,
            },
            "motion": {"fadeMs": 250},
            "canvas": {"width": WIDTH, "height": HEIGHT, "fps": FPS},
        }
    },
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
print(f"Wrote {OUT / 'example-manifest.json'}")
print(f"Total duration: {t + DUR_CTA:.1f}s, assets: {len(assets)}")
