#!/usr/bin/env python3
"""Build a clean catalog from raw 2RP Supabase fetch."""
import json
from pathlib import Path
from collections import defaultdict

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "projects" / "2rp-launch-video" / "2rp-assets" / "2rp_assets_raw.json"
OUT = ROOT / "projects" / "2rp-launch-video" / "2rp-assets"
OUT.mkdir(parents=True, exist_ok=True)

with RAW.open() as f:
    raw = json.load(f)


def media_url(item):
    """Return the best playable video URL if available."""
    return item.get("cloudflare_playback_hls_url") or item.get("hlsUrl") or None


def valid_video_url(url: str) -> bool:
    """Return True if the HLS manifest (or direct URL) is currently reachable."""
    if not url:
        return False
    try:
        r = requests.head(url, timeout=15, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


def thumbnail_url(item):
    """Return the best thumbnail URL."""
    return item.get("cloudflare_thumbnail_url") or item.get("backup_thumbnail_url") or item.get("thumbnailUrl") or None


def creator_of(item):
    """Best-effort creator/artist name."""
    return (
        item.get("creator_display_name")
        or item.get("creator_username")
        or item.get("creator")
        or item.get("author")
        or ""
    )


def pick_top_art(items, n=3):
    """Pick the first n featured art pieces with both video and thumbnail."""
    ranked = sorted(items, key=lambda x: (
        bool(media_url(x)) and bool(thumbnail_url(x)),
        x.get("featured_on_2rf", False),
        x.get("created_at", "")
    ), reverse=True)
    return ranked[:n]


def pick_top_resources(items, n=3, resource_type=None, preferred_names=None, validate_urls=False):
    """Pick the first n resources that have a usable media preview.

    If preferred_names is provided, resources whose names contain any of those
    strings (case-insensitive) are promoted to the front, preserving the order
    given in preferred_names.

    When validate_urls is True, only resources whose video URL is currently
    reachable (HTTP 200) are kept, and the working URL is stored on the item
    as ``video_url`` so downstream renderers use it directly.
    """
    preferred_names = [p.lower() for p in (preferred_names or [])]

    def score(item):
        if not item or (resource_type and item.get("type") != resource_type):
            return (10**9, False, False, "")
        media = item.get("media") or {}
        fb = item.get("fallbackMedia") or []
        thumb = thumbnail_url(media) or any(thumbnail_url(m) for m in fb)
        vid = media_url(media) or any(media_url(m) for m in fb)
        name = (item.get("name") or "").lower()
        pref_idx = next((i for i, p in enumerate(preferred_names) if p in name), len(preferred_names))
        return (pref_idx, not (bool(thumb) and bool(vid)), item.get("admin_status") != "Curated", item.get("created_at", ""))

    ranked = sorted(items, key=score)

    def first_working_url(item):
        media = item.get("media") or {}
        fb = item.get("fallbackMedia") or []
        for src in [media] + list(fb):
            url = media_url(src)
            if url and valid_video_url(url):
                return url
        return None

    picked = []
    for item in ranked:
        if len(picked) >= n:
            break
        if resource_type and item.get("type") != resource_type:
            continue
        working = first_working_url(item) if validate_urls else (media_url(item.get("media") or {}) or first_working_url(item))
        if validate_urls and not working:
            continue
        item.setdefault("video_url", working or media_url(item.get("media") or {}))
        picked.append(item)

    return picked


def pick_top_posts(items, n=3):
    """Pick first n posts with cover media."""
    ranked = sorted(items, key=lambda x: (bool(x.get("cover") and (thumbnail_url(x["cover"]) or media_url(x["cover"]))), x.get("published_at") or x.get("created_at", "")), reverse=True)
    return ranked[:n]


def pick_top_news(items, n=3):
    """Pick first n community news topics with media."""
    ranked = sorted(items, key=lambda x: (len(x.get("mediaUrls", [])), x.get("date", "")), reverse=True)
    return ranked[:n]


# Build art catalog
art_catalog = []
for item in raw.get("art_gallery", []):
    art_catalog.append({
        "id": item["id"],
        "title": item.get("title") or item.get("description", "")[:60],
        "creator": creator_of(item),
        "description": item.get("description", ""),
        "type": item.get("type"),
        "featured_on_2rf": item.get("featured_on_2rf", False),
        "created_at": item.get("created_at"),
        "member_id": item.get("member_id"),
        "video_url": media_url(item),
        "thumbnail_url": thumbnail_url(item),
        "page_url": f"https://banodoco.ai/art/{item.get('id')}",
        "generation_note": "Submitted via /submit/art; shown in ArtGallerySection with curated/featured filter.",
    })

# Build resources catalog
resources_catalog = []
for item in raw.get("resources", []):
    media = item.get("media") or {}
    fb = item.get("fallbackMedia") or []
    thumb = thumbnail_url(media) or next((thumbnail_url(m) for m in fb), None)
    vid = media_url(media) or next((media_url(m) for m in fb), None)
    resources_catalog.append({
        "id": item["id"],
        "slug": item.get("slug"),
        "name": item.get("name"),
        "creator": creator_of(item),
        "description": item.get("description", ""),
        "type": item.get("type"),
        "admin_status": item.get("admin_status"),
        "lora_type": item.get("lora_type"),
        "lora_base_model": item.get("lora_base_model"),
        "model_variant": item.get("model_variant"),
        "download_link": item.get("download_link"),
        "lora_link": item.get("lora_link"),
        "created_at": item.get("created_at"),
        "video_url": vid,
        "thumbnail_url": thumb,
        "page_url": f"https://banodoco.ai/resources/{item.get('slug') or item['id']}",
        "generation_note": "Submitted via /submit/resource; shown in ResourceGrid on /2rp.",
    })

# Build posts catalog
posts_catalog = []
for item in raw.get("posts", []):
    cover = item.get("cover") or {}
    posts_catalog.append({
        "id": item["id"],
        "slug": item.get("slug"),
        "title": item.get("title"),
        "render_mode": item.get("renderMode"),
        "published_at": item.get("publishedAt") or item.get("created_at"),
        "video_url": media_url(cover),
        "thumbnail_url": thumbnail_url(cover),
        "page_url": f"https://banodoco.ai/posts/{item.get('slug') or item['id']}",
        "generation_note": "Submitted via /submit/post; shown in Posts section on /2rp.",
    })

# Build community news catalog
news_catalog = []
for item in raw.get("community_news", []):
    media = item.get("mediaUrls", [])
    news_catalog.append({
        "title": item.get("title", ""),
        "channel_name": item.get("channel_name"),
        "date": item.get("date"),
        "main_text": item.get("main_text", ""),
        "media_count": len(media),
        "videos": [m["url"] for m in media if m.get("type") == "video"],
        "images": [m["url"] for m in media if m.get("type") == "image"],
        "page_url": "https://banodoco.ai/2rp#news",
        "generation_note": "Auto-generated from Discord daily summaries; shown in CommunityNewsSection.",
    })

# Build hero artists catalog
hero_catalog = []
for item in raw.get("hero_artists", []):
    hero_catalog.append({
        "id": item["id"],
        "title": item.get("title"),
        "creator": creator_of(item),
        "video_url": media_url(item),
        "thumbnail_url": thumbnail_url(item),
        "page_url": f"https://banodoco.ai/art/{item.get('id')}",
        "generation_note": "Featured hero cycler on /2rp; selected from VisualFrisson, fabdream, emmacatnip featured_on_2rf videos.",
    })

# Picks for the launch video — separate LoRAs and workflows.
# Include hero artists in art picks so the featured VisualFrisson piece can lead.
art_picks_pool = raw.get("art_gallery", []) + raw.get("hero_artists", [])
seen_ids = set()
art_picks_pool_unique = []
for item in art_picks_pool:
    if item["id"] in seen_ids:
        continue
    seen_ids.add(item["id"])
    art_picks_pool_unique.append(item)

video_picks = {
    "hero": pick_top_art(raw.get("hero_artists", []), 3),
    "art": pick_top_art(art_picks_pool_unique, 3),
    "loras": pick_top_resources(raw.get("resources", []), 3, resource_type="lora"),
    "workflows": pick_top_resources(
        raw.get("resources", []), 3, resource_type="workflow",
        preferred_names=[
            "Advanced remixing with acestep 1.5 approaching real time",
            "Unleash the power of denoising with the NKD Sigmas Curve",
            "Animate a LEGO shot",
        ],
        validate_urls=True,
    ),
    "posts": pick_top_posts(raw.get("posts", []), 3),
    "community_news": pick_top_news(raw.get("community_news", []), 3),
    "agents": [],  # No approved agents currently displayed
}

# Force VisualFrisson's "Everyone All at Once" to lead the Art section,
# replacing Atlas's "Chronicle Gem" so the three art picks are
# VisualFrisson, fabdream, EmmaCatnip.
_vf_hero = next((item for item in raw.get("hero_artists", [])
                 if item.get("title") == "Everyone All at Once"), None)
if _vf_hero is not None:
    video_picks["art"] = [item for item in video_picks["art"]
                          if item.get("title") not in ("Everyone All at Once", "Chronicle Gem")]
    video_picks["art"].insert(0, _vf_hero)
    video_picks["art"] = video_picks["art"][:3]

# Small clip start offsets (seconds) to skip opening cuts/jumps in selected assets.
for i, item in enumerate(video_picks.get("art", [])):
    if i == 0 and item.get("title") == "Everyone All at Once":
        item["clip_start_offset"] = 1.5
    elif i == 2 and item.get("title") == "Temporal Drift":
        item["clip_start_offset"] = 1.5


catalog = {
    "meta": {
        "fetched_at": raw["fetched_at"],
        "page_url": raw["page_url"],
        "total_counts": {
            "hero_artists": len(hero_catalog),
            "art_gallery": len(art_catalog),
            "resources": len(resources_catalog),
            "posts": len(posts_catalog),
            "community_news": len(news_catalog),
            "agents": 0,
        },
    },
    "sections": {
        "hero": {
            "label": "Hero",
            "description": "Full-screen editorial hero with cycling artist videos.",
            "assets": hero_catalog,
        },
        "art": {
            "label": "Art",
            "description": "Curated / All art grid shown in ArtGallerySection.",
            "assets": art_catalog,
        },
        "resources": {
            "label": "Resources",
            "description": "LoRAs, workflows, and tools shown in ResourceGrid.",
            "assets": resources_catalog,
        },
        "posts": {
            "label": "Posts",
            "description": "Published posts shown in Posts section.",
            "assets": posts_catalog,
        },
        "community_news": {
            "label": "Community News",
            "description": "Discord daily-summary dispatches shown in CommunityNewsSection.",
            "assets": news_catalog,
        },
        "agents": {
            "label": "Art Agents",
            "description": "Agent node catalog. Currently no approved nodes are displayed on /2rp.",
            "assets": [],
        },
        "briefing": {
            "label": "Briefing",
            "description": "Hardcoded YouTube briefing embeds.",
            "assets": [
                {"title": "Community Briefing — April", "youtube_id": "6oBWkKcq59A", "caption": "Latest integrations & releases"},
                {"title": "Community Briefing — March", "youtube_id": "6oBWkKcq59A", "caption": "Research notes & spotlights"},
                {"title": "Community Briefing — February", "youtube_id": "6oBWkKcq59A", "caption": "Milestones & ships"},
            ],
        },
        "community_montage": {
            "label": "Community Montage",
            "description": "Local animated collage using /assorted_propaganda/*.webp frames.",
            "assets": [{"pattern": "/assorted_propaganda/{1..25}.webp", "frame_count": 25, "source": "local public assets"}],
        },
    },
}

with (OUT / "catalog.json").open("w") as f:
    json.dump(catalog, f, indent=2)

with (OUT / "video-picks.json").open("w") as f:
    json.dump(video_picks, f, indent=2)

print(f"Wrote {OUT / 'catalog.json'}")
print(f"Wrote {OUT / 'video-picks.json'}")
print("Counts:", catalog["meta"]["total_counts"])
