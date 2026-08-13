"""Hermetic park24 fixture integrity: the 24-clip complex-gate fixture.

No VLM — this runs in default CI.  It proves the fixture is a valid timeline
slice AND that the two planted mismatches are exactly the failure mode the
epic targets: **hash-verified, semantically wrong**.

- CL09's media file is byte-identical to CL03's (a frame reused out of
  narrative order).  Both registry entries carry matching content_sha256, so
  resolution classifies CL09 as ``verified_original`` — hashes cannot flag it.
- CL16's media is the Paris poster (foreign scene).  Also ``verified_original``.

Only visual understanding of the rendered pages can catch either.  The live
gate (test_timeline_visualize_gate_park24.py) proves a VLM can.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from astrid.core.foundation.project_paths import project_dir
from astrid.core.project.project import create_project
from astrid.core.timeline.resolution import classify_registry
from astrid.core.timeline.snapshot import acquire_snapshot

TESTS_ROOT = Path(__file__).resolve().parents[2]
SLICE_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "park24_slice"
MEDIA_DIR = TESTS_ROOT / "fixtures" / "timeline_visualize" / "park24_media"
TIMELINE_ULID = "01KZXA59P24YX2WR8JZC4D85K7"


def _project_with_media(tmp_projects_root: Path) -> tuple[Path, Path]:
    create_project("park24-hermetic", root=tmp_projects_root)
    root = project_dir("park24-hermetic", root=tmp_projects_root)
    timeline = root / "timelines" / TIMELINE_ULID
    shutil.copytree(SLICE_DIR, timeline)
    snapshot = acquire_snapshot(timeline, project_slug="park24-hermetic")
    classified = classify_registry(snapshot.registry, project_root=root)
    for key, integrity in classified.items():
        if isinstance(integrity.path, str) and integrity.path.lower().endswith(".png"):
            source = MEDIA_DIR / f"{key}.png"
            assert source.exists(), f"park24 media missing: {source}"
            target = root / "sources" / str(integrity.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    return root, timeline


def test_park24_slice_is_valid_24_clip_timeline(tmp_projects_root: Path) -> None:
    root, timeline = _project_with_media(tmp_projects_root)
    snapshot = acquire_snapshot(timeline, project_slug="park24-hermetic", project_root=root)
    clips = snapshot.assembly["clips"]
    assert len(clips) == 24
    assert [clip["id"] for clip in clips] == [
        f"park-frame-{index:02d}" for index in range(1, 25)
    ]
    # All on one visual track, ordered, non-overlapping.
    assert {clip["track"] for clip in clips} == {"storyboard"}
    for left, right in zip(clips, clips[1:]):
        assert left["at"] + left["hold"] <= right["at"] + 1e-6
    assert snapshot.head_version == 2  # config_replaced + asset_registry_replaced


def test_park24_media_all_verified_original_including_mismatches(
    tmp_projects_root: Path,
) -> None:
    root, timeline = _project_with_media(tmp_projects_root)
    snapshot = acquire_snapshot(timeline, project_slug="park24-hermetic", project_root=root)
    classified = classify_registry(snapshot.registry, project_root=root)
    states = {
        key: integrity.state
        for key, integrity in classified.items()
        if key.startswith("park-frame-")
    }
    assert len(states) == 24
    assert set(states.values()) == {"verified_original"}, states


def test_park24_planted_mismatches_are_hash_invisible(tmp_projects_root: Path) -> None:
    """The planted mismatches must pass hashing — ground truth cannot catch
    them; only visual reading can."""
    root, timeline = _project_with_media(tmp_projects_root)
    snapshot = acquire_snapshot(timeline, project_slug="park24-hermetic", project_root=root)
    assets = snapshot.registry["assets"]
    # CL09 == CL03 media bytes (duplicate frame) yet a distinct registry entry.
    assert assets["park-frame-09"]["content_sha256"] == assets["park-frame-03"]["content_sha256"]
    assert assets["park-frame-09"]["file"] != assets["park-frame-03"]["file"]
    # CL16 == the Paris poster bytes (foreign scene), distinct from neighbors.
    poster = (MEDIA_DIR / "park-frame-16.png").read_bytes()
    assert hashlib.sha256(poster).hexdigest() == assets["park-frame-16"]["content_sha256"]
    assert assets["park-frame-16"]["content_sha256"] != assets["park-frame-15"]["content_sha256"]
    assert assets["park-frame-16"]["content_sha256"] != assets["park-frame-17"]["content_sha256"]
    # The other 21 frames are pairwise distinct.
    digests = [
        assets[f"park-frame-{index:02d}"]["content_sha256"]
        for index in range(1, 25)
        if index not in (9, 16)
    ]
    assert len(set(digests)) == 22, "expected 22 distinct frames (24 minus dup+foreign)"


def test_park24_root_renders_two_pages_with_all_24_clips(tmp_projects_root: Path) -> None:
    """The complex gate depends on the root splitting across pages with all
    clip cards present (24 strips)."""
    from astrid.packs.rendering.executors.timeline_visualize.layout import layout_timeline
    from astrid.packs.rendering.executors.timeline_visualize.model import build_model
    from astrid.packs.rendering.executors.timeline_visualize.navigation import build_identity_map
    from astrid.packs.rendering.executors.timeline_visualize.scope import select_scope

    root, timeline = _project_with_media(tmp_projects_root)
    snapshot = acquire_snapshot(timeline, project_slug="park24-hermetic", project_root=root)
    model = build_model(snapshot, project_root=root)
    identity_map = build_identity_map(
        model, root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid, timeline_ulid=model.timeline_ulid,
    )
    scope = select_scope(model, kind="timeline")
    pages = layout_timeline(model, identity_map, scope, layout="time-scaled")
    clip_ids = [
        obj.display_id
        for page in pages
        for obj in page.objects
        if obj.kind == "clip"
    ]
    assert len(pages) == 2
    assert len(clip_ids) == 24
    assert clip_ids[0] == "TL01.CL01"
    assert clip_ids[-1] == "TL01.CL24"
    # The focus ring anchors the first primary clip on each page (CL01 on
    # page 1, CL23 on page 2 — page-local first primary).
    rings = [obj.display_id for page in pages for obj in page.objects if obj.kind == "focus_ring"]
    assert rings == ["TL01.CL01", "TL01.CL23"]
