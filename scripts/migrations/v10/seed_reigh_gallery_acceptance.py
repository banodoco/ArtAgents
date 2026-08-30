"""Seed an explicit, deterministic Reigh gallery acceptance project.

This fixture exists because the migrated corpus contains only three historical
image-generation tasks, all with a single output.  It would be dishonest to
reinterpret imported reference art as generated variants.  Instead this
command creates a clearly named acceptance project through Astrid's normal
repositories and task-completion transaction:

* 12 image generations;
* 2 real, byte-distinct variants per generation;
* one four-shot timeline whose groups reference only their own clips; and
* a registry backed by the exact managed media ids produced by the tasks.

Dry-run is the default. ``--apply`` requires exclusive ownership of the store,
so stop ``astrid serve`` first. Re-running with ``--apply`` is receipt-idempotent.
No SQLite row is ever written directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

PROJECT_SLUG = "reigh-gallery-acceptance"
PROJECT_NAME = "Reigh Gallery Acceptance"
TIMELINE_SLUG = "shot-matrix"
GENERATION_COUNT = 12
VARIANTS_PER_GENERATION = 2
SHOT_COUNT = 4
STAMP = "2026-08-27T12:00:00.000Z"
MUSIC_PROJECT_SLUG = "music3-cybernetic"
MUSIC_TIMELINE_SLUG = "gallery-acceptance"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Return one standards-compliant RGB PNG using only the stdlib."""

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, level=9))
        + _chunk(b"IEND", b"")
    )


def _palette(index: int, variant: int) -> tuple[int, int, int]:
    return (
        35 + ((index * 37 + variant * 61) % 190),
        35 + ((index * 73 + variant * 29) % 190),
        35 + ((index * 19 + variant * 97) % 190),
    )


def _read_counts(root: Path, client: Any | None = None) -> dict[str, Any]:
    """Read acceptance counts through the workspace runtime.

    ``root`` is retained as the caller-owned staging directory for API
    compatibility; it is never opened as a local authority.
    """
    del root
    if client is None:
        return {
            "project_present": False,
            "generations": 0,
            "variants": 0,
            "timelines": 0,
            "pinned_shot_groups": 0,
        }
    shown = client.projects.show(PROJECT_SLUG)
    if not shown.ok or shown.data is None:
        return {"project_present": False, "generations": 0, "variants": 0, "timelines": 0, "pinned_shot_groups": 0}
    project_id = str(shown.data.get("id") or shown.data.get("project_id"))
    generations = client.generations.list(project_id)
    generation_rows = generations.data.get("items", []) if generations.ok and isinstance(generations.data, dict) else []
    variants = 0
    for generation in generation_rows:
        generation_id = str(generation.get("id") or generation.get("generation_id"))
        page = client.generations.variants(project_id, generation_id)
        if page.ok and isinstance(page.data, dict):
            variants += len(page.data.get("items", []))
    timelines = client.timelines.list(project_id)
    timeline_rows = timelines.data if timelines.ok and isinstance(timelines.data, list) else []
    pinned = 0
    for timeline in timeline_rows:
        config = timeline.get("config") if isinstance(timeline, dict) else None
        groups = config.get("pinnedShotGroups") if isinstance(config, dict) else None
        pinned += len(groups) if isinstance(groups, list) else 0
    return {"project_present": True, "generations": len(generation_rows), "variants": variants, "timelines": len(timeline_rows), "pinned_shot_groups": pinned}


def _require_ok(result: Any, operation: str) -> dict[str, Any]:
    if not result.ok or result.data is None:
        detail = result.error.as_dict() if result.error is not None else None
        raise RuntimeError(f"{operation} failed: {detail}")
    return dict(result.data)


def _ensure_music_acceptance_timeline(client: Any) -> bool:
    """Give the real migrated cover-image generation one honest shot proof.

    The music project is optional in isolated tests.  When present, its one
    historical image generation is already projected by
    ``repair_generation_gallery.py``; this adds only a document timeline that
    references that exact primary media row.
    """

    shown = client.projects.show(MUSIC_PROJECT_SLUG)
    if not shown.ok or shown.data is None:
        return False
    project_id = str(shown.data["id"])
    listed = client.generations.list(project_id)
    rows = listed.data.get("items", []) if listed.ok and isinstance(listed.data, dict) else []
    primary = next((row for row in rows if row.get("metadata", {}).get("primary_media_id")), None)
    if primary is None:
        return False
    _require_ok(
        client.timelines.create(
            project=project_id,
            slug=MUSIC_TIMELINE_SLUG,
            name="Music cover gallery acceptance",
            config={
                "tracks": [{"id": "V1", "kind": "visual", "label": "Cover art"}],
                "clips": [{
                    "id": "cover-image",
                    "at": 0,
                    "track": "V1",
                    "clipType": "media",
                    "asset": "cover-image",
                    "hold": 4,
                    "label": "Generated cover",
                }],
                "pinnedShotGroups": [{
                    "shotId": "music-cover-shot",
                    "name": "Generated Cover",
                    "trackId": "V1",
                    "clipIds": ["cover-image"],
                    "mode": "images",
                }],
                "theme": "banodoco-default",
                "theme_overrides": {"visual": {"canvas": {"width": 1280, "height": 720, "fps": 24}}},
            },
            registry={
                "assets": {
                    "cover-image": {
                        "media_id": primary["metadata"]["primary_media_id"],
                        "type": "image/png",
                        "generationId": primary.get("generation_id", primary.get("id")),
                    }
                }
            },
            set_default=True,
            idempotency_key="fixture:reigh-gallery:music-timeline:v1",
        ),
        "music acceptance timeline create",
    )
    return True


def _apply(root: Path, client: Any) -> None:
    project = _require_ok(
        client.projects.create(
            slug=PROJECT_SLUG,
            name=PROJECT_NAME,
            settings={"fixture_kind": "reigh-gallery-acceptance-v1"},
            idempotency_key="fixture:reigh-gallery:project:v1",
        ),
        "project create",
    )
    project_id = str(project.get("id") or project.get("project_id"))
    client.tasks.register_capability(
        "fixture.reigh_gallery_image",
        "sha256:" + hashlib.sha256(b"fixture.reigh_gallery_image:v1").hexdigest(),
        status="ready",
        idempotency_key="fixture:reigh-gallery:capability:v1",
    )
    client.tasks.register_executor(
        executor_id="reigh-acceptance-fixture",
        capabilities=["fixture.reigh_gallery_image"],
        idempotency_key="fixture:reigh-gallery:executor:v1",
    )
    primary_media: list[dict[str, str]] = []

    staging_root = root / ".astrid" / "media" / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reigh-gallery-fixture-", dir=staging_root) as raw_staging:
        staging = Path(raw_staging)
        for index in range(GENERATION_COUNT):
            key = f"fixture:reigh-gallery:generation:{index:02d}:v1"
            task = _require_ok(
                client.tasks.create(
                    project_id=project_id,
                    capability="fixture.reigh_gallery_image",
                    spec={"fixture": "reigh-gallery-acceptance-v1", "prompt": f"Deterministic colour study {index + 1}"},
                    input_manifest=[],
                    idempotency_key=f"{key}:create",
                ),
                f"task {index} create",
            )
            task_id = str(task.get("id") or task.get("task_id"))
            claim = _require_ok(
                client.tasks.claim(
                    executor_id="reigh-acceptance-fixture",
                    capability_ids=["fixture.reigh_gallery_image"],
                    idempotency_key=f"{key}:claim",
                ),
                f"task {index} claim",
            )
            if str(claim.get("task_id")) != task_id:
                raise RuntimeError(f"task {index} claim selected an unexpected task")

            outputs: list[dict[str, Any]] = []
            imported: list[dict[str, Any]] = []
            for variant_index in range(VARIANTS_PER_GENERATION):
                filename = f"study-{index + 1:02d}-variant-{variant_index + 1}.png"
                path = staging / filename
                path.write_bytes(_solid_png(320, 180, _palette(index, variant_index)))
                media = _require_ok(
                    client.media.import_file(project=project_id, path=path, idempotency_key=f"{key}:media:{variant_index}"),
                    f"task {index} media {variant_index}",
                )
                imported.append(media)
                outputs.append({"digest": media["digest"], "media_type": "image/png", "name": filename})

            _require_ok(
                client.tasks.settle(
                    str(claim["attempt_id"]),
                    lease_id=str(claim["lease_id"]),
                    fence=int(claim["fence"]),
                    outputs=outputs,
                    idempotency_key=f"{key}:settle",
                ),
                f"task {index} settle",
            )
            generation_id = f"reigh-gallery-generation-{index + 1:02d}"
            generation = _require_ok(
                client.generations.create(
                    project=project_id,
                    generation_id=generation_id,
                    type="image",
                    source_task_id=task_id,
                    metadata={"fixture": "reigh-gallery-acceptance-v1", "primary_media_id": imported[0]["object_id"]},
                    idempotency_key=f"{key}:generation",
                ),
                f"generation {index} create",
            )
            generation_id = str(generation.get("generation_id") or generation.get("id"))
            for variant_index, media in enumerate(imported):
                _require_ok(
                    client.generations.create_variant(
                        generation_id,
                        variant_id=f"{generation_id}-variant-{variant_index + 1}",
                        object_id=media["object_id"],
                        variant_type="original" if variant_index == 0 else "alternate",
                        metadata={"fixture_variant": variant_index},
                        idempotency_key=f"{key}:variant:{variant_index}",
                    ),
                    f"generation {index} variant {variant_index}",
                )
            primary_media.append({"id": imported[0]["object_id"], "type": "image/png"})

        clips: list[dict[str, Any]] = []
        registry_assets: dict[str, dict[str, str]] = {}
        groups: list[dict[str, Any]] = []
        for index, media in enumerate(primary_media):
            asset_id = f"study-{index + 1:02d}"
            clip_id = f"clip-{index + 1:02d}"
            clips.append({
                "id": clip_id,
                "at": index * 2,
                "track": "V1",
                "clipType": "media",
                "asset": asset_id,
                "hold": 2,
                "label": f"Study {index + 1}",
            })
            registry_assets[asset_id] = {"media_id": media["id"], "type": media["type"]}
        for shot_index in range(SHOT_COUNT):
            start = shot_index * 3
            groups.append({
                "shotId": f"acceptance-shot-{shot_index + 1}",
                "name": f"Acceptance Shot {shot_index + 1}",
                "trackId": "V1",
                "clipIds": [f"clip-{index + 1:02d}" for index in range(start, start + 3)],
                "mode": "images",
            })
        _require_ok(
            client.timelines.create(
                project=project_id,
                slug=TIMELINE_SLUG,
                name="Gallery and shot acceptance matrix",
                config={
                    "tracks": [{"id": "V1", "kind": "visual", "label": "Generated images"}],
                    "clips": clips,
                    "pinnedShotGroups": groups,
                    "theme": "banodoco-default",
                    "theme_overrides": {"visual": {"canvas": {"width": 1280, "height": 720, "fps": 24}}},
                },
                registry={"assets": registry_assets},
                set_default=True,
                idempotency_key="fixture:reigh-gallery:timeline:v1",
            ),
            "timeline create",
        )
        _ensure_music_acceptance_timeline(client)


def seed_reigh_gallery_acceptance(root: Path, *, apply: bool = False) -> dict[str, Any]:
    expected = {
        "generations": GENERATION_COUNT,
        "variants": GENERATION_COUNT * VARIANTS_PER_GENERATION,
        "timelines": 1,
        "pinned_shot_groups": SHOT_COUNT,
    }
    if apply:
        from astrid.sdk.client import AstridClient

        with AstridClient.open() as client:
            before = _read_counts(root, client)
            if not before.get("project_present") or any(before.get(key) != value for key, value in expected.items()):
                _apply(root, client)
            after = _read_counts(root, client)
    else:
        before = _read_counts(root)
        after = _read_counts(root)
    ok = all(after[key] == value for key, value in expected.items()) if apply else True
    return {
        "ok": ok,
        "mode": "apply" if apply else "dry-run",
        "root": str(root),
        "project": PROJECT_SLUG,
        "before": before,
        "after": after,
        "expected": expected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed deterministic Reigh gallery acceptance data")
    parser.add_argument("--root", required=True, help="Astrid projects root")
    parser.add_argument("--apply", action="store_true", help="apply through Astrid repositories")
    parser.add_argument("--report", default=None, help="optional JSON report path")
    args = parser.parse_args()
    report = seed_reigh_gallery_acceptance(Path(args.root), apply=args.apply)
    encoded = json.dumps(report, indent=2, sort_keys=True)
    print(encoded)
    if args.report:
        Path(args.report).write_text(encoded + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
