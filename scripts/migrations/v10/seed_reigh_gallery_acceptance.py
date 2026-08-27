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
import json
import sqlite3
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


def _read_counts(root: Path) -> dict[str, Any]:
    db = root / ".astrid" / "astrid.sqlite3"
    if not db.is_file():
        return {
            "project_present": False,
            "generations": 0,
            "variants": 0,
            "timelines": 0,
            "pinned_shot_groups": 0,
        }
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT id FROM projects WHERE slug = ?", (PROJECT_SLUG,)).fetchone()
        if row is None:
            return {
                "project_present": False,
                "generations": 0,
                "variants": 0,
                "timelines": 0,
                "pinned_shot_groups": 0,
            }
        project_id = str(row[0])
        generation_count = int(conn.execute(
            "SELECT COUNT(*) FROM generations WHERE project_id=? AND deleted_at IS NULL",
            (project_id,),
        ).fetchone()[0])
        variant_count = int(conn.execute(
            "SELECT COUNT(*) FROM generation_variants v JOIN generations g ON g.id=v.generation_id "
            "WHERE g.project_id=? AND g.deleted_at IS NULL",
            (project_id,),
        ).fetchone()[0])
        timelines = conn.execute(
            "SELECT document_json FROM timelines WHERE project_id=?",
            (project_id,),
        ).fetchall()
        pinned = 0
        for timeline in timelines:
            config = json.loads(str(timeline[0]))
            groups = config.get("pinnedShotGroups") if isinstance(config, dict) else None
            pinned += len(groups) if isinstance(groups, list) else 0
        return {
            "project_present": True,
            "generations": generation_count,
            "variants": variant_count,
            "timelines": len(timelines),
            "pinned_shot_groups": pinned,
        }
    finally:
        conn.close()


def _require_ok(result: Any, operation: str) -> dict[str, Any]:
    if not result.ok or result.data is None:
        detail = result.error.as_dict() if result.error is not None else None
        raise RuntimeError(f"{operation} failed: {detail}")
    return dict(result.data)


def _apply(root: Path) -> None:
    from astrid.core.io.media_import import prepare_media_file
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs.shots.generation_repository import GenerationRepository
    from astrid.sdk.client import AstridClient

    with AstridClient.open(projects_root=root) as client:
        project = _require_ok(
            client.projects.create(
                slug=PROJECT_SLUG,
                name=PROJECT_NAME,
                settings={"fixture_kind": "reigh-gallery-acceptance-v1"},
                idempotency_key="fixture:reigh-gallery:project:v1",
            ),
            "project create",
        )
        project_id = str(project["id"])
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
                        spec={
                            "fixture": "reigh-gallery-acceptance-v1",
                            "prompt": f"Deterministic colour study {index + 1}",
                            "output_policy": {"create_generation": True},
                        },
                        input_manifest=[],
                        available_at=STAMP,
                        max_attempts=1,
                        idempotency_key=f"{key}:create",
                    ),
                    f"task {index} create",
                )
                task_id = str(task["id"])

                claim = UnitOfWork(client.app.writer).run(
                    lambda u, key=key: client.app.tasks.claim(
                        u,
                        project_id=project_id,
                        idempotency_key=f"{key}:claim",
                        actor_kind="system",
                        executor_id="reigh-acceptance-fixture",
                        lease_seconds=3600,
                        now=STAMP,
                    )
                )
                if claim is None or claim.task.id != task_id:
                    raise RuntimeError(f"task {index} claim selected an unexpected task")
                started = UnitOfWork(client.app.writer).run(
                    lambda u, key=key, claim=claim: client.app.tasks.start(
                        u,
                        project_id=project_id,
                        task_id=task_id,
                        attempt_id=claim.attempt.id,
                        expected_status_version=claim.attempt.status_version,
                        lease_id=claim.attempt.lease_id,
                        idempotency_key=f"{key}:start",
                        actor_kind="system",
                        now=STAMP,
                    )
                )

                outputs: list[dict[str, Any]] = []
                for variant_index in range(VARIANTS_PER_GENERATION):
                    filename = f"study-{index + 1:02d}-variant-{variant_index + 1}.png"
                    path = staging / filename
                    path.write_bytes(_solid_png(320, 180, _palette(index, variant_index)))
                    outputs.append({
                        "ordinal": variant_index,
                        "is_primary": variant_index == 0,
                        "role": "result" if variant_index == 0 else "artifact",
                        "label": filename,
                        "path": filename,
                        "variant_type": "original" if variant_index == 0 else "alternate",
                        "name": "Original" if variant_index == 0 else "Alternate colour",
                        "variant_params": {"fixture_variant": variant_index},
                        "prepared": prepare_media_file(path, root=staging),
                    })

                completed = UnitOfWork(client.app.writer).run(
                    lambda u, key=key, claim=claim, started=started, outputs=outputs: client.app.tasks.complete(
                        u,
                        project_id=project_id,
                        task_id=task_id,
                        attempt_id=claim.attempt.id,
                        lease_id=claim.attempt.lease_id,
                        expected_status_version=started.status_version,
                        idempotency_key=f"{key}:complete",
                        outputs=outputs,
                        media_repo=client.app.media,
                        generation_repo=GenerationRepository(),
                        generation_request={
                            "type": "image",
                            "params": {
                                "fixture": "reigh-gallery-acceptance-v1",
                                "prompt": f"Deterministic colour study {index + 1}",
                            },
                        },
                        actor_kind="system",
                        now=STAMP,
                    )
                )
                primary = next(output for output in completed.outputs if output.is_primary)
                if primary.media_id is None:
                    raise RuntimeError(f"task {index} primary output has no media id")
                primary_media.append({"id": str(primary.media_id), "type": "image/png"})

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


def seed_reigh_gallery_acceptance(root: Path, *, apply: bool = False) -> dict[str, Any]:
    before = _read_counts(root)
    if apply:
        _apply(root)
    after = _read_counts(root)
    expected = {
        "generations": GENERATION_COUNT,
        "variants": GENERATION_COUNT * VARIANTS_PER_GENERATION,
        "timelines": 1,
        "pinned_shot_groups": SHOT_COUNT,
    }
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
