"""Build the park24 timeline slice fixture — 24 real-frame visual clips with
two planted, hash-verified mismatches that only a VLM can catch.

Design (matches the complex-gate intent):
- 24 visual clips in a coherent desert-plant -> water-reveal narrative order,
  one per real render from the desert-plant-growth project (fal is exhausted,
  these are the real frames already on disk).
- CL09's media file is a byte-identical copy of CL03's frame.  The registry
  records both with matching content_sha256, so hashing verifies CL09 as
  ``verified_original`` — a frame reused out of narrative order, invisible to
  hashes.
- CL16's media is the Paris poster (foreign scene).  Hash-verified, obviously
  not a plant render.

Outputs:
- ``tests/fixtures/timeline_visualize/park24_media/`` — the real frame files
  (media the gate copies into a project's sources/).
- ``tests/fixtures/timeline_visualize/park24_slice/`` — a valid timeline
  slice (identity, display, config_replaced + asset_registry_replaced event
  chain, registry.json, assembly.head.json) the gate copies as the timeline.

Deterministic: fixed UUID/ULID/timestamps; event hashes derived from content.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from astrid.core.timeline.events.schema.serialize import with_event_hash
from astrid.core.timeline.events.schema.types import TimelineActor, TimelineEvent

REPO = Path(__file__).resolve().parents[1]
SRC_PROJECT = Path(
    "/Users/peteromalley/Documents/reigh-workspace/Astrid/projects/desert-plant-growth"
)
MEDIA_OUT = REPO / "tests/fixtures/timeline_visualize/park24_media"
SLICE_OUT = REPO / "tests/fixtures/timeline_visualize/park24_slice"
POSTER = Path(
    "/Users/peteromalley/Documents/reigh-workspace/Astrid/projects/ados-talks/sources/poster-paris.png"
)

TIMELINE_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
TIMELINE_ULID = "01KZXA59P24YX2WR8JZC4D85K7"
TS = "2026-08-11T12:00:00Z"

#: Narrative order: desert plant frames, coherent story progression.
FRAME_NAMES = [
    "01-01-shot1-start.png",
    "01-01-shot1-close-thread.png",
    "01-shot2-wide-contact-thick-feeder.png",
    "01-06-shot3-close-start.png",
    "02-02-shot1-branch-pullback.png",
    "02-02-shot1-mid.png",
    "02-07-shot3-rising-mid.png",
    "03-03-shot1-distant-lake.png",
    "03-03-shot1-end.png",
    "03-08-shot3-wide-end.png",
    "04-04-shot2-approach-gap.png",
    "04-shot2-contact-wide.png",
    "04-shot2-start.png",
    "05-05-shot2-shore-wrap.png",
    "05-shot2-mid.png",
    "05-shot2-wrap-end.png",
    "06-water-reveal.png",
    "07-shot3-start.png",
    "08-shot3-mid.png",
    "05-existing-shot3-giant-fan-end.png",
    "01-shot3-close-start-continuity.png",
    "02-shot2-wrap-end-clean-water.png",
    "02-shot3-rising-mid-continuity.png",
    "03-distant-lake-16x9-crop-test.png",
]

#: Planted mismatches (1-indexed clip positions).
DUP_CLIP = 9   # shows a byte-copy of CL03's frame
DUP_SRC = 3    # the clip whose frame CL09 reuses
FOREIGN_CLIP = 16  # shows the Paris poster (foreign scene)


def _find_frame(name: str) -> Path:
    hits = [p for p in SRC_PROJECT.rglob(name) if "debug" not in str(p) and ".capture" not in str(p)]
    if not hits:
        raise SystemExit(f"frame not found: {name}")
    return hits[0]


def main() -> int:
    MEDIA_OUT.mkdir(parents=True, exist_ok=True)
    SLICE_OUT.mkdir(parents=True, exist_ok=True)

    # 1. Copy the 24 real frames into media/ (park-frame-01..24.png) and
    #    compute their content hashes + real pixel resolutions.  The
    #    duplicate CL09 is a byte copy of CL03's file under its own name;
    #    the foreign CL16 is the poster.
    media_hashes: dict[str, str] = {}
    media_resolutions: dict[str, str] = {}
    for index, name in enumerate(FRAME_NAMES, start=1):
        dest = MEDIA_OUT / f"park-frame-{index:02d}.png"
        if not dest.exists():
            shutil.copyfile(_find_frame(name), dest)
        media_hashes[f"park-frame-{index:02d}"] = hashlib.sha256(dest.read_bytes()).hexdigest()
        with Image.open(dest) as image:
            media_resolutions[f"park-frame-{index:02d}"] = f"{image.width}x{image.height}"

    # CL09 duplicate: byte-identical to CL03's file (own registry key).
    # Unconditional — the duplicate must win over any earlier real frame.
    dup_bytes = (MEDIA_OUT / "park-frame-03.png").read_bytes()
    (MEDIA_OUT / "park-frame-09.png").write_bytes(dup_bytes)
    media_hashes["park-frame-09"] = hashlib.sha256(dup_bytes).hexdigest()
    media_resolutions["park-frame-09"] = media_resolutions["park-frame-03"]

    # CL16 foreign: the Paris poster (always overwrite — the foreign frame
    # must be the poster even if an earlier run left the real frame there).
    poster_dest = MEDIA_OUT / "park-frame-16.png"
    shutil.copyfile(POSTER, poster_dest)
    media_hashes["park-frame-16"] = hashlib.sha256(poster_dest.read_bytes()).hexdigest()
    with Image.open(poster_dest) as image:
        media_resolutions["park-frame-16"] = f"{image.width}x{image.height}"

    # 2. Build the assembly event chain.
    clip_configs: list[dict] = []
    at = 0.0
    for index in range(1, 25):
        hold = 4.0 if index % 3 else 4.6667
        clip_configs.append(
            {
                "asset": f"park-frame-{index:02d}",
                "at": round(at, 4),
                "clipType": "media",
                "generation": {"input_index": index - 1, "role": "storyboard-input"},
                "hold": round(hold, 4),
                "id": f"park-frame-{index:02d}",
                "track": "storyboard",
            }
        )
        at += hold

    config = {
        "clips": clip_configs,
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"fps": 24, "height": 720, "width": 1280}}
        },
        "tracks": [
            {"app": {"scaleAppliesToPositionedClips": True}, "fit": "cover",
             "id": "storyboard", "kind": "visual", "label": "Storyboard"}
        ],
    }

    assets: dict[str, dict] = {}
    for index in range(1, 25):
        key = f"park-frame-{index:02d}"
        assets[key] = {
            "content_sha256": media_hashes[key],
            "file": f"park24/{key}.png",
            "resolution": media_resolutions[key],
            "type": "image/png",
        }

    actor = TimelineActor(id="agent:fixture-builder", display="park24 fixture builder", type="agent")
    events: list[TimelineEvent] = []
    prev_hash: str | None = None
    for kind, payload in (
        ("timeline.config_replaced", {"config": config}),
        ("timeline.asset_registry_replaced", {"registry": {"assets": assets}}),
    ):
        event = TimelineEvent.new(
            timeline_id=TIMELINE_ID,
            ts=TS,
            actor=actor,
            kind=kind,  # type: ignore[arg-type]
            payload=payload,
            prev_hash=prev_hash,
        )
        event = with_event_hash(event, prev_hash=prev_hash)
        events.append(event)
        prev_hash = event.hash

    # 3. identity + display.
    (SLICE_OUT / "assembly.identity.json").write_text(
        json.dumps(
            {
                "backend": "local_fs",
                "created_at": TS,
                "display": {
                    "is_default": True,
                    "name": "Park24 Desert Plant Walk",
                    "schema_version": 1,
                    "slug": "park24-plant-walk",
                },
                "provenance": "created",
                "schema_version": 1,
                "timeline_id": TIMELINE_ID,
                "timeline_ulid": TIMELINE_ULID,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    (SLICE_OUT / "display.json").write_text(
        json.dumps(
            {"is_default": True, "name": "Park24 Desert Plant Walk",
             "schema_version": 1, "slug": "park24-plant-walk"},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    # 4. assembly.jsonl + registry.json + head sidecar.
    (SLICE_OUT / "assembly.jsonl").write_text(
        "\n".join(json.dumps(e.to_json_obj(), sort_keys=True, separators=(",", ":"))
                  for e in events)
        + "\n",
        encoding="utf-8",
    )
    (SLICE_OUT / "registry.json").write_text(
        json.dumps({"assets": assets}, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    (SLICE_OUT / "assembly.head.json").write_text(
        json.dumps(
            {
                "event_count": len(events),
                "last_event_id": events[-1].event_id,
                "last_hash": events[-1].hash,
                "timeline_id": TIMELINE_ID,
                "version": len(events),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print(f"park24 slice -> {SLICE_OUT}")
    print(f"  clips: 24, assets: 24, dup CL{DUP_CLIP}=CL{DUP_SRC}, foreign CL{FOREIGN_CLIP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
