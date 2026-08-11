#!/usr/bin/env python3
"""Add per-section type breakdown to 2rp catalog."""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "projects" / "2rp-launch-video" / "2rp-assets" / "catalog.json"

with CATALOG.open() as f:
    catalog = json.load(f)

# Section -> inferred type when asset lacks explicit type.
SECTION_INFERRED_TYPE = {
    "hero": "video",
    "art": "video",
    "posts": "post",
    "community_news": "news",
    "briefing": "briefing",
    "community_montage": "montage",
    "agents": "agent",
}

# Add type breakdown per section.
for section_key, section in catalog["sections"].items():
    assets = section.get("assets", [])
    by_type = defaultdict(list)
    for asset in assets:
        t = (
            asset.get("type")
            or asset.get("render_mode")
            or asset.get("resource_type")
            or SECTION_INFERRED_TYPE.get(section_key, "unknown")
        )
        # Enrich asset record with normalized type.
        asset["asset_kind"] = t
        by_type[t].append(asset.get("id") or asset.get("title") or "unknown")
    section["type_breakdown"] = {k: len(v) for k, v in sorted(by_type.items())}
    section["by_type"] = dict(by_type)

# Top-level type summary across all assets.
all_types = defaultdict(int)
for section in catalog["sections"].values():
    for t, count in section["type_breakdown"].items():
        all_types[t] += count

catalog["meta"]["type_summary"] = dict(sorted(all_types.items()))

with CATALOG.open("w") as f:
    json.dump(catalog, f, indent=2)

print("Updated catalog.json with type breakdown.")
print("Type summary:", catalog["meta"]["type_summary"])
