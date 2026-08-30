from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from astrid.core.timeline.snapshot import TimelineSnapshot, acquire_snapshot
from astrid.core.io.media_import import managed_media_path
from astrid.packs.rendering.executors.timeline_visualize.model import (
    ClipModel,
    IntervalFrames,
    IntervalSeconds,
    TimelineInspectionModel,
    build_model,
    transition_effective_intervals,
    transition_mounted_intervals,
)
from astrid.packs.rendering.executors.timeline_visualize.scope import Scope, select_scope
from astrid.packs.rendering.executors.timeline_visualize.snapshot_digest import (
    canonical_json_bytes,
    sha256_bytes,
)

TESTS_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_ROOT / "fixtures" / "timeline_visualize"
SLICE_DIR = FIXTURE_ROOT / "desert_slice"
TRUTH = json.loads((FIXTURE_ROOT / "desert_truth.json").read_text(encoding="utf-8"))
PROJECT_SLUG = "desert-plant-growth"


def _digest(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _file_state(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _prepared_snapshot(tmp_path: Path) -> tuple[TimelineSnapshot, Path, Path]:
    """Portable slice plus synthetic contained media for full R5 classification."""

    project_root = tmp_path / "project"
    timeline_dir = project_root / "timelines" / TRUTH["timeline"]["ulid"]
    timeline_dir.parent.mkdir(parents=True)
    shutil.copytree(SLICE_DIR, timeline_dir)
    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)

    registry = deepcopy(snapshot.registry)
    for key, entry in registry["assets"].items():
        payload = f"portable R7 media: {key}".encode("utf-8")
        target = project_root / "sources" / entry["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        if "content_sha256" in entry:
            entry["content_sha256"] = hashlib.sha256(payload).hexdigest()

    snapshot = replace(
        snapshot,
        registry=registry,
        registry_sha256=_digest(registry),
    )
    return snapshot, project_root, timeline_dir


def _with_assembly(
    snapshot: TimelineSnapshot,
    assembly: dict,
    *,
    registry: dict | None = None,
) -> TimelineSnapshot:
    normalized_registry = {"assets": {}} if registry is None else registry
    return replace(
        snapshot,
        assembly=deepcopy(assembly),
        registry=deepcopy(normalized_registry),
        assembly_sha256=_digest(assembly),
        registry_sha256=_digest(normalized_registry),
        media_hashes={},
    )


@pytest.fixture
def desert(
    tmp_path: Path,
) -> tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path]:
    snapshot, project_root, timeline_dir = _prepared_snapshot(tmp_path)
    return build_model(snapshot, project_root=project_root), snapshot, project_root, timeline_dir


def test_build_model_desert_truth_and_integrity(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    model, snapshot, _project_root, _timeline_dir = desert

    assert model.timeline_uuid == TRUTH["timeline"]["uuid"]
    assert model.timeline_ulid == TRUTH["timeline"]["ulid"]
    assert model.slug == TRUTH["timeline"]["slug"]
    assert model.fps == 24
    assert len(model.tracks) == 2
    assert len(model.clips) == 5
    assert model.extents.composition_frames == 2352
    assert model.extents.composition_seconds == 98.0
    assert model.extents.visual_frames == 332
    assert model.extents.visual_seconds == 332 / 24
    assert model.extents.audible_frames == 2352
    assert model.extents.fps == 24
    assert model.compositor_version == "0.0.6"
    assert model.transition_default_frames == 12
    assert model.snapshot_sns == snapshot.sns()
    assert model.registry_keys == frozenset(snapshot.registry["assets"])
    states = {key: value.state for key, value in model.media_integrity.items()}
    assert states == {
        "plant-frame-1": "verified_original",
        "plant-frame-2": "verified_original",
        "plant-frame-3": "verified_original",
        "plant-frame-4": "verified_original",
        "toccata-fugue": "hash_unrecorded",
    }

    # Authored source seconds remain distinct from compositor-quantized seconds.
    frame_four = next(clip for clip in model.clips if clip.clip_id == "plant-frame-4")
    assert frame_four.authored.start == pytest.approx(11.4333)
    assert frame_four.authored.end == pytest.approx(13.8667)
    assert frame_four.frames.end_frame / model.fps == 332 / 24


def test_managed_visualization_uses_admitted_runtime_media_snapshot(
    tmp_path: Path,
) -> None:
    snapshot, project_root, _timeline_dir = _prepared_snapshot(tmp_path)
    payload = b"runtime admitted visualization asset"
    digest = hashlib.sha256(payload).hexdigest()
    managed = managed_media_path(project_root.parent, digest)
    managed.parent.mkdir(parents=True, exist_ok=True)
    managed.write_bytes(payload)
    registry = {
        "assets": {
            "managed": {
                "file": str(managed),
                "media_id": "object-1",
                "content_sha256": digest,
                "type": "image/png",
            }
        }
    }
    managed_snapshot = replace(
        snapshot,
        registry=registry,
        registry_sha256=_digest(registry),
        media_hashes={},
    )
    runtime_media = [
        {
            "object_id": "object-1",
            "content_hash": f"sha256:{digest}",
            "media_type": "image/png",
        }
    ]

    denied = build_model(managed_snapshot, project_root=project_root)
    admitted = build_model(
        managed_snapshot,
        project_root=project_root,
        media_snapshot=runtime_media,
    )

    assert denied.media_integrity["managed"].state == "unsupported"
    assert admitted.media_integrity["managed"].state == "verified_original"
    assert admitted.media_integrity["managed"].path == str(managed.resolve())


def test_visualization_resolution_import_is_local_authority_free() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import astrid.packs.rendering.executors.timeline_visualize.run; "
            "print('sqlite3' in sys.modules); "
            "print(any(name.startswith('astrid.core.repositories') for name in sys.modules))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]


def test_track_config_and_bottom_to_top_paint_indices(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    model, snapshot, _project_root, _timeline_dir = desert
    storyboard, audio = model.tracks
    assert (storyboard.config_order, storyboard.paint_index) == (0, 0)
    assert (audio.config_order, audio.paint_index) == (1, 1)

    z_order = {
        "theme_overrides": {"visual": {"canvas": {"fps": 30}}},
        "tracks": [
            {"id": "v1", "kind": "visual", "label": "Top"},
            {"id": "v2", "kind": "visual", "label": "Bottom"},
            {"id": "a1", "kind": "audio", "label": "Audio"},
        ],
        "clips": [
            {"id": "top", "track": "v1", "clipType": "media", "at": 0, "hold": 1},
            {"id": "bottom", "track": "v2", "clipType": "media", "at": 0, "hold": 1},
            {"id": "audio", "track": "a1", "clipType": "media", "at": 0, "hold": 1},
        ],
    }
    z_model = build_model(_with_assembly(snapshot, z_order))
    assert [(track.track_id, track.paint_index) for track in z_model.tracks] == [
        ("v1", 1),
        ("v2", 0),
        ("a1", 2),
    ]
    assert z_model.tracks[0].paint_index == max(
        track.paint_index for track in z_model.tracks if track.kind == "visual"
    )


def test_clip_model_legacy_construction_defaults_mounted_to_frames() -> None:
    frames = IntervalFrames(12, 42, 30)
    clip = ClipModel(
        clip_id="legacy",
        track_id="v1",
        authored=IntervalSeconds(0.4, 1.4),
        frames=frames,
        effective=frames.as_seconds(),
        speed=1.0,
        transition=None,
        source=None,
        kind="media",
    )
    assert clip.mounted == frames


def test_desert_clip_frames_match_frozen_windows(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    model, _snapshot, _project_root, _timeline_dir = desert
    expected = {
        item["id"]: (item["frame_start"], item["frame_end"])
        for item in TRUTH["clip_windows"]
    }
    assert {
        clip.clip_id: (clip.frames.start_frame, clip.frames.end_frame)
        for clip in model.clips
    } == expected
    assert all(clip.mounted == clip.frames for clip in model.clips)
    assert [clip.clip_id for clip in model.clips] == [
        "plant-frame-1",
        "plant-frame-2",
        "plant-frame-3",
        "plant-frame-4",
        "toccata-fugue",
    ]


def test_transition_effective_intervals_mirror_group_retiming_and_clipping(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    desert_model, snapshot, _project_root, _timeline_dir = desert
    assert transition_effective_intervals(desert_model) == {
        clip.clip_id: clip.frames.as_seconds() for clip in desert_model.clips
    }
    assert transition_mounted_intervals(desert_model) == {
        clip.clip_id: clip.frames for clip in desert_model.clips
    }
    assert all(clip.mounted == clip.frames for clip in desert_model.clips)
    assert all(clip.effective == clip.frames.as_seconds() for clip in desert_model.clips)

    transition_timeline = {
        "theme_overrides": {"visual": {"canvas": {"fps": 30}}},
        "tracks": [{"id": "v1", "kind": "visual", "label": "Visual"}],
        "pinnedShotGroups": [
            {
                "shotId": "before-overlap",
                "clipIds": ["from"],
                "start": 60 / 30,
                "end": 75 / 30,
            }
        ],
        "clips": [
            {
                "id": "from",
                "track": "v1",
                "clipType": "media",
                "at": 0,
                "hold": 3,
                "transition": {"id": "cross-fade", "durationFrames": 15},
            },
            {"id": "to", "track": "v1", "clipType": "media", "at": 2, "hold": 3},
        ],
    }
    model = build_model(_with_assembly(snapshot, transition_timeline))
    from_clip, to_clip = model.clips
    assert (from_clip.frames.start_frame, from_clip.frames.end_frame) == (0, 90)
    assert (to_clip.frames.start_frame, to_clip.frames.end_frame) == (60, 150)
    # TimelineComposition.tsx:208-237 mounts the group at F=0, keeps the
    # source Sequence mounted for Df=90 frames, and mounts the destination at
    # F + toOffset = 75.  The composition clips its scheduled end from 165 to
    # 150, leaving the physical cross-fade overlap [75, 90).
    assert from_clip.mounted == IntervalFrames(0, 90, 30)
    assert to_clip.mounted == IntervalFrames(75, 150, 30)
    assert transition_mounted_intervals(model) == {
        "from": from_clip.mounted,
        "to": to_clip.mounted,
    }
    assert from_clip.effective == IntervalSeconds(0, 75 / 30)

    # TimelineComposition.tsx:208-237 schedules the destination Sequence at
    # frame 75, consumes its 15-frame transition head, and clips its scheduled
    # group end (165) to the 150-frame composition.  Effective start is thus 90,
    # not raw destination start 60 + a naïvely applied transition.
    assert to_clip.effective == IntervalSeconds(90 / 30, 150 / 30)
    assert transition_effective_intervals(model) == {
        "from": from_clip.effective,
        "to": to_clip.effective,
    }

    at_60 = select_scope(model, kind="timestamp", at_seconds=60 / 30)
    assert at_60.context_frames == 90
    assert at_60.emphasized_clip_ids == ("from",)

    # Both mounted Sequences contribute during the physical cross-fade.
    at_80 = select_scope(model, kind="timestamp", at_seconds=80 / 30)
    assert at_80.emphasized_clip_ids == ("from", "to")
    at_90 = select_scope(model, kind="timestamp", at_seconds=90 / 30)
    assert at_90.emphasized_clip_ids == ("to",)

    before_overlap = select_scope(model, kind="range", start=60 / 30, end=75 / 30)
    assert before_overlap.clip_ids == ("from",)
    overlap = select_scope(model, kind="range", start=75 / 30, end=90 / 30)
    assert overlap.clip_ids == ("from", "to")

    authored_shot = select_scope(model, kind="shot", ref="before-overlap")
    assert (authored_shot.start_frame, authored_shot.end_frame) == (60, 75)
    assert authored_shot.clip_ids == ("from",)
    assert authored_shot.emphasized_clip_ids == ("from",)

    to_scope = select_scope(model, kind="clip", clip_id="to", context_seconds=0)
    assert (to_scope.start_frame, to_scope.end_frame) == (75, 150)


def test_cold_scopes_use_closed_open_compositor_intersections(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    model, _snapshot, _project_root, _timeline_dir = desert

    whole = select_scope(model, kind="timeline")
    assert whole.start_frame == 0
    assert whole.end_frame == 2352
    assert whole.clip_ids == tuple(clip.clip_id for clip in model.clips)

    selected_range = select_scope(model, kind="range", start=0, end=5)
    assert (selected_range.start_frame, selected_range.end_frame) == (0, 120)
    assert selected_range.clip_ids == (
        "plant-frame-1",
        "plant-frame-2",
        "toccata-fugue",
    )

    timestamp = select_scope(model, kind="timestamp", at_seconds=12.0)
    assert (timestamp.start_frame, timestamp.end_frame) == (216, 360)
    assert timestamp.context_frames == 72
    assert timestamp.clip_ids == (
        "plant-frame-3",
        "plant-frame-4",
        "toccata-fugue",
    )
    # The active compositor stack is visual; audio remains an explicit context
    # contributor instead of being mislabeled as a paint layer.
    assert timestamp.emphasized_clip_ids == ("plant-frame-4",)

    past_end = select_scope(model, kind="timestamp", at_seconds=1_000)
    assert (past_end.start_frame, past_end.end_frame) == (2352, 2352)
    assert past_end.clip_ids == () and past_end.emphasized_clip_ids == ()
    assert past_end.warnings

    clip_scope = select_scope(
        model,
        kind="clip",
        clip_id="plant-frame-2",
        context_seconds=0,
    )
    assert (clip_scope.start_frame, clip_scope.end_frame) == (86, 205)
    assert clip_scope.clip_ids == ("plant-frame-2", "toccata-fugue")
    assert clip_scope.emphasized_clip_ids == ("plant-frame-2",)

    padded_clip_scope = select_scope(model, kind="clip", clip_id="plant-frame-2")
    assert padded_clip_scope.context_frames == 72
    assert padded_clip_scope.clip_ids == ("plant-frame-2", "toccata-fugue")

    asset_scope = select_scope(model, kind="asset", asset_key="plant-frame-3")
    assert asset_scope.clip_ids == ("plant-frame-3",)
    assert asset_scope.emphasized_clip_ids == ("plant-frame-3",)

    fallback_model = replace(
        model,
        clips=tuple(
            replace(clip, asset_keys=()) if clip.clip_id == "plant-frame-3" else clip
            for clip in model.clips
        ),
    )
    assert select_scope(
        fallback_model,
        kind="asset",
        asset_key="plant-frame-3",
    ).clip_ids == ("plant-frame-3",)

    missing_shot = select_scope(model, kind="shot", ref="SH-missing")
    assert missing_shot.clip_ids == ()
    assert missing_shot.emphasized_clip_ids == ()
    assert missing_shot.start_frame is None and missing_shot.end_frame is None
    assert missing_shot.warnings and "pinnedShotGroups" in missing_shot.warnings[0]


def test_timestamp_scope_retains_exact_requested_instant(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    model, _snapshot, _project_root, _timeline_dir = desert

    scope = select_scope(model, kind="timestamp", at_seconds=2.0)

    assert scope.at_seconds == 2.0
    assert (scope.start_frame, scope.end_frame) == (0, 120)
    assert scope.requested_start_frame is None
    assert scope.requested_end_frame is None


def test_range_scope_retains_exact_requested_bounds_when_clipped(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    model, _snapshot, _project_root, _timeline_dir = desert

    scope = select_scope(model, kind="range", start=97.0, end=120.0)

    assert (scope.start_frame, scope.end_frame) == (2328, 2880)
    assert (scope.requested_start_frame, scope.requested_end_frame) == (2328, 2880)
    assert scope.at_seconds is None
    assert scope.clip_ids == ("toccata-fugue",)
    assert scope.warnings


def test_scope_new_fields_have_backward_compatible_defaults() -> None:
    scope = Scope("timeline", None, 0, 0, (), (), 0)

    assert scope.at_seconds is None
    assert scope.requested_start_frame is None
    assert scope.requested_end_frame is None


def test_shot_scope_prefers_authored_bounds_and_keeps_intersecting_tracks(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    _model, snapshot, project_root, _timeline_dir = desert
    assembly = deepcopy(snapshot.assembly)
    assembly["pinnedShotGroups"] = [
        {
            "shotId": "growth-middle",
            "trackId": "storyboard",
            "clipIds": ["plant-frame-2"],
            "start": 3.6,
            "end": 8.5667,
        }
    ]
    model = build_model(_with_assembly(snapshot, assembly, registry=snapshot.registry), project_root=project_root)
    scope = select_scope(model, kind="shot", ref="growth-middle")
    assert (scope.start_frame, scope.end_frame) == (86, 206)
    assert scope.clip_ids == ("plant-frame-2", "toccata-fugue")
    assert scope.emphasized_clip_ids == ("plant-frame-2",)


def test_model_and_scopes_are_deterministic_and_do_not_write(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    first, snapshot, project_root, timeline_dir = desert
    before = _file_state(project_root)

    second = build_model(snapshot, project_root=project_root)
    scopes_first = (
        select_scope(first, kind="timeline"),
        select_scope(first, kind="range", start=0, end=5),
        select_scope(first, kind="clip", clip_id="plant-frame-2", context_seconds=0),
        select_scope(first, kind="asset", asset_key="plant-frame-3"),
        select_scope(first, kind="timestamp", at_seconds=12),
    )
    scopes_second = (
        select_scope(second, kind="timeline"),
        select_scope(second, kind="range", start=0, end=5),
        select_scope(second, kind="clip", clip_id="plant-frame-2", context_seconds=0),
        select_scope(second, kind="asset", asset_key="plant-frame-3"),
        select_scope(second, kind="timestamp", at_seconds=12),
    )

    assert first == second
    assert scopes_first == scopes_second
    assert _file_state(project_root) == before
    assert timeline_dir.is_dir()


def test_model_and_scope_import_graph_has_no_repair_or_mutation_api() -> None:
    package_dir = (
        Path(__file__).resolve().parents[3]
        / "astrid"
        / "packs"
        / "rendering"
        / "executors"
        / "timeline_visualize"
    )
    imported: set[str] = set()
    for name in ("model.py", "scope.py"):
        tree = ast.parse((package_dir / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

    forbidden = (
        "timeline.crud",
        "timeline.projection",
        "timeline_storyboard",
    )
    assert not any(token in module for module in imported for token in forbidden)


def test_rootless_build_never_guesses_local_asset_paths(
    desert: tuple[TimelineInspectionModel, TimelineSnapshot, Path, Path],
) -> None:
    _rooted, snapshot, _project_root, _timeline_dir = desert
    model = build_model(snapshot)
    assert set(value.state for value in model.media_integrity.values()) == {"missing"}
    assert all(value.path is None for value in model.media_integrity.values())
