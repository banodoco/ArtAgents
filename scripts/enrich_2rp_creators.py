#!/usr/bin/env python3
"""Enrich 2RP video-picks with creator Discord handles + avatars from Supabase.

Reads projects/2rp-launch-video/2rp-assets/video-picks.json, fetches member
rows from the brain-of-bndc Supabase `members` table, adds creator fields,
and downloads Discord avatars locally.
"""
import json
import os
import urllib.request
from pathlib import Path

from supabase import create_client, ClientOptions

ROOT = Path(__file__).resolve().parent.parent
PICKS = ROOT / "projects" / "2rp-launch-video" / "2rp-assets" / "video-picks.json"
CATALOG = ROOT / "projects" / "2rp-launch-video" / "2rp-assets" / "catalog.json"
AVATAR_DIR = ROOT / "projects" / "2rp-launch-video" / "launch-video" / "assets" / "avatars"
WEBSITE_ENV = Path.home() / "Documents" / "banodoco-workspace" / "banodoco-website" / ".env"


def _load_env(path: Path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _supabase_client():
    env = _load_env(WEBSITE_ENV)
    url = env.get("VITE_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key, options=ClientOptions(auto_refresh_token=False))


def _member_ids_from_picks(picks: dict) -> set:
    ids = set()
    for key in ["hero", "art", "loras", "workflows", "posts"]:
        for item in picks.get(key, []):
            mid = item.get("member_id")
            if mid:
                ids.add(str(mid))
    return ids


def _member_ids_from_catalog(catalog: dict) -> set:
    ids = set()
    for section in catalog.get("sections", {}).values():
        for item in section.get("assets", []):
            mid = item.get("member_id")
            if mid:
                ids.add(str(mid))
    return ids


def _fetch_members(supabase, member_ids: set) -> dict:
    if not member_ids:
        return {}
    rows = {}
    ids = list(member_ids)
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        resp = supabase.table("members").select(
            "member_id, username, global_name, server_nick, avatar_url, stored_avatar_url"
        ).in_("member_id", batch).execute()
        for row in resp.data or []:
            rows[str(row["member_id"])] = row
    return rows


def _display_name(row: dict) -> str:
    return row.get("global_name") or row.get("server_nick") or row.get("username") or "Unknown"


def _avatar_url(row: dict) -> str | None:
    return row.get("stored_avatar_url") or row.get("avatar_url")


def _download_avatar(url: str, mid: str) -> str | None:
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".png"
    if ".gif" in url.split("?")[0]:
        ext = ".gif"
    local = AVATAR_DIR / f"{mid}{ext}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, local.open("wb") as f:
            f.write(resp.read())
        return str(local.relative_to(ROOT / "projects" / "2rp-launch-video" / "launch-video"))
    except Exception as exc:
        print(f"WARN failed avatar download {url}: {exc}")
        return None


def _enrich_item(item: dict, members: dict) -> bool:
    mid = str(item.get("member_id", ""))
    if not mid or mid not in members:
        return False
    row = members[mid]
    item["creator_username"] = row.get("username") or ""
    item["creator_display_name"] = _display_name(row)
    item["creator_avatar_url"] = _avatar_url(row)
    avatar_local = None
    if item["creator_avatar_url"]:
        avatar_local = _download_avatar(item["creator_avatar_url"], mid)
    item["creator_avatar_local"] = avatar_local
    return True


def main():
    with PICKS.open() as f:
        picks = json.load(f)
    with CATALOG.open() as f:
        catalog = json.load(f)

    supabase = _supabase_client()
    member_ids = _member_ids_from_picks(picks) | _member_ids_from_catalog(catalog)
    print(f"Fetching {len(member_ids)} member profiles...")
    members = _fetch_members(supabase, member_ids)
    print(f"Got {len(members)} member rows.")

    enriched_count = 0
    for key in ["hero", "art", "loras", "workflows", "posts"]:
        for item in picks.get(key, []):
            if _enrich_item(item, members):
                enriched_count += 1
                print(f"  picks/{key}: {item.get('title', item.get('name', ''))} by {item['creator_display_name']}")

    for section in catalog.get("sections", {}).values():
        for item in section.get("assets", []):
            if _enrich_item(item, members):
                enriched_count += 1
                print(f"  catalog/{section.get('label')}: {item.get('title', item.get('name', ''))} by {item['creator_display_name']}")

    with PICKS.open("w") as f:
        json.dump(picks, f, indent=2)
    with CATALOG.open("w") as f:
        json.dump(catalog, f, indent=2)

    print(f"Enriched {enriched_count} items. Wrote {PICKS} and {CATALOG}")


if __name__ == "__main__":
    main()
