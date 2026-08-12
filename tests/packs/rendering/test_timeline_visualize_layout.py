from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from astrid.core.timeline.snapshot import TimelineSnapshot, acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.layout import (
    PAGE_H,
    PAGE_W,
    Box,
    LayoutObject,
    layout_timeline,
    serialize_view_map,
)
from astrid.packs.rendering.executors.timeline_visualize.model import (
    ClipModel,
    IntervalFrames,
    IntervalSeconds,
    ModelExtents,
    TimelineInspectionModel,
    TrackModel,
    build_model,
)
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    IdentityMap,
    build_identity_map,
)
from astrid.packs.rendering.executors.timeline_visualize.schemas import (
    DEFS_PATH,
    SCHEMAS,
)
from astrid.packs.rendering.executors.timeline_visualize.scope import Scope, select_scope

TESTS_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_ROOT / "fixtures" / "timeline_visualize"
SLICE_DIR = FIXTURE_ROOT / "desert_slice"
PROJECT_SLUG = "desert-plant-growth"
TIMELINE_UUID = "ed70ef66-43da-4182-9f14-69361c6c5e10"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"


@pytest.fixture
def desert(
    tmp_path: Path,
) -> tuple[TimelineInspectionModel, IdentityMap, TimelineSnapshot, Scope]:
    timeline_dir = tmp_path / "timeline"
    shutil.copytree(SLICE_DIR, timeline_dir)
    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)
    model = build_model(snapshot)
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    scope = select_scope(model, kind="timeline")
    return model, identity_map, snapshot, scope


def _synthetic_model(
    intervals: list[tuple[int, int, str]],
    *,
    tracks: tuple[TrackModel, ...] | None = None,
    fps: int = 30,
    composition_frames: int | None = None,
) -> tuple[TimelineInspectionModel, IdentityMap, Scope]:
    if tracks is None:
        tracks = (TrackModel("visual", "visual", 0, 0, "Visual"),)
    clips = tuple(
        ClipModel(
            clip_id=f"clip-{index + 1}",
            track_id=track_id,
            authored=IntervalSeconds(start / fps, end / fps),
            frames=IntervalFrames(start, end, fps),
            effective=IntervalSeconds(start / fps, end / fps),
            speed=1.0,
            transition=None,
            source=None,
            kind="media",
        )
        for index, (start, end, track_id) in enumerate(intervals)
    )
    extent = composition_frames
    if extent is None:
        extent = max((clip.frames.end_frame for clip in clips), default=1)
    visual_ids = {track.track_id for track in tracks if track.kind == "visual"}
    visual_end = max(
        (clip.frames.end_frame for clip in clips if clip.track_id in visual_ids),
        default=0,
    )
    audible_end = max(
        (
            clip.frames.end_frame
            for clip in clips
            if next(track for track in tracks if track.track_id == clip.track_id).kind
            == "audio"
        ),
        default=0,
    )
    model = TimelineInspectionModel(
        timeline_uuid=TIMELINE_UUID,
        timeline_ulid=TIMELINE_ULID,
        slug="synthetic-layout",
        fps=fps,
        tracks=tracks,
        clips=clips,
        extents=ModelExtents(
            composition_frames=extent,
            composition_seconds=extent / fps,
            visual_frames=visual_end,
            visual_seconds=visual_end / fps,
            audible_frames=audible_end,
            fps=fps,
        ),
        compositor_version="0.0.6",
        transition_default_frames=12,
        registry_keys=frozenset(),
        media_integrity={},
        snapshot_sns="SNS:" + "a" * 64,
    )
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    scope = Scope(
        kind="timeline",
        ref=None,
        start_frame=0,
        end_frame=extent,
        clip_ids=tuple(clip.clip_id for clip in clips),
        emphasized_clip_ids=(),
        context_frames=0,
    )
    return model, identity_map, scope


def _primary_clips(pages) -> list[LayoutObject]:
    return [item for page in pages for item in page.objects if item.kind == "clip"]


def test_desert_time_scaled_keeps_full_axis_and_one_frame_artifacts(desert) -> None:
    model, identity_map, _snapshot, scope = desert
    pages = layout_timeline(model, identity_map, scope, layout="time-scaled")

    assert [(page.width, page.height) for page in pages] == [
        (PAGE_W, PAGE_H),
        (PAGE_W, PAGE_H),
    ]
    assert [page.scope_bounds_frames for page in pages] == [(0, 2160), (2160, 2352)]
    assert pages[0].scope_bounds_frames[0] == 0
    assert pages[-1].scope_bounds_frames[1] == 2352
    assert all(
        first.scope_bounds_frames[1] == following.scope_bounds_frames[0]
        for first, following in zip(pages, pages[1:])
    )

    clips = _primary_clips(pages)
    assert [clip.display_id for clip in clips] == [
        identity_map.lookup_semantic("clip", model_clip.clip_id)
        for model_clip in model.clips
    ]
    assert len(clips) == 5 == len({clip.display_id for clip in clips})
    assert [clip.lane_index for clip in clips[:4]] == [0, 0, 0, 0]

    by_ref = {clip.display_id: clip for clip in clips}
    frame_2 = by_ref[identity_map.lookup_semantic("clip", "plant-frame-2")]
    frame_3 = by_ref[identity_map.lookup_semantic("clip", "plant-frame-3")]
    frame_4 = by_ref[identity_map.lookup_semantic("clip", "plant-frame-4")]
    assert frame_2.box.x + frame_2.box.w < frame_3.box.x
    assert frame_3.box.x + frame_3.box.w > frame_4.box.x
    assert any(
        item.kind == "gap_marker"
        and item.label.startswith("1fr gap")
        and "→" in item.label
        for item in pages[0].objects
    )
    assert any(
        item.kind == "gap_marker"
        and item.label.startswith("1fr overlap")
        and "→" in item.label
        for item in pages[0].objects
    )
    detail = next(
        item
        for item in pages[0].objects
        if item.kind == "label"
        and item.label
        and item.label.startswith("visual detail ends")
    )
    assert "332fr" in detail.label
    assert "authored end=13.8667s" in detail.label

    ticks = [item for item in pages[0].objects if item.kind == "ruler_tick"]
    ruler_labels = [
        item
        for item in pages[0].objects
        if item.kind == "label"
        and item.label
        and item.label.partition("fr · ")[0].isdigit()
    ]
    assert ticks
    assert len(ruler_labels) == len(ticks)
    assert all(tick.label is None for tick in ticks)
    assert [label.box for label in ruler_labels] == [
        Box(tick.box.x, tick.box.y + tick.box.h, 320.0, 30.0)
        for tick in ticks
    ]


def test_time_scaled_distance_is_proportional_to_frame_distance() -> None:
    model, identity_map, scope = _synthetic_model(
        [(0, 30, "visual"), (60, 90, "visual")],
        composition_frames=300,
    )
    pages = layout_timeline(model, identity_map, scope, layout="time-scaled")
    first, second = _primary_clips(pages)

    # Equal one-second durations; their starts are two seconds apart.
    assert (second.box.x - first.box.x) / first.box.w == pytest.approx(2.0)


def test_linear_cards_follow_clip_order_label_time_and_continue(desert) -> None:
    model, identity_map, _snapshot, scope = desert
    pages = layout_timeline(
        model,
        identity_map,
        scope,
        layout="linear",
        max_objects_per_page=2,
    )

    assert len(pages) == 3
    clips = _primary_clips(pages)
    assert [clip.display_id for clip in clips] == [
        identity_map.lookup_semantic("clip", model_clip.clip_id)
        for model_clip in model.clips
    ]
    assert all("start=" in clip.label for clip in clips)
    assert all("end=" in clip.label for clip in clips)
    assert all("duration=" in clip.label for clip in clips)
    assert all("authored=" in clip.label for clip in clips)
    assert "13.8667s" in clips[3].label
    assert all(page.continuation for page in pages)
    assert all(
        any(item.kind == "continuation" for item in page.objects) for page in pages
    )

    axis_ticks = [item for item in pages[0].objects if item.kind == "ruler_tick"]
    axis_labels = [
        item
        for item in pages[0].objects
        if item.kind == "label" and item.label and item.label.startswith("scope ")
    ]
    assert [item.label for item in axis_labels] == [
        "scope start=0fr/0.0000s",
        "scope end=2352fr/98.0000s",
    ]
    assert [label.box for label in axis_labels] == [
        Box(tick.box.x, tick.box.y + tick.box.h, 320.0, 30.0)
        for tick in axis_ticks
    ]


def test_lanes_are_topmost_first_while_z_order_is_bottom_to_top() -> None:
    tracks = (
        TrackModel("top", "visual", 0, 1, "Top"),
        TrackModel("bottom", "visual", 1, 0, "Bottom"),
    )
    model, identity_map, scope = _synthetic_model(
        [(0, 60, "top"), (0, 60, "bottom")],
        tracks=tracks,
        composition_frames=60,
    )
    page = layout_timeline(model, identity_map, scope, layout="time-scaled")[0]

    lanes = [item for item in page.objects if item.kind == "track_lane"]
    assert [lane.lane_index for lane in lanes] == [0, 1]
    assert "Top" in lanes[0].label
    assert "Bottom" in lanes[1].label
    clips = _primary_clips((page,))
    assert clips[0].lane_index == 0
    assert clips[1].lane_index == 1
    assert clips[0].z_order > clips[1].z_order


def test_dense_pagination_is_complete_unique_and_deterministic() -> None:
    intervals = [(index * 30, (index + 1) * 30, "visual") for index in range(60)]
    model, identity_map, scope = _synthetic_model(
        intervals,
        composition_frames=1800,
    )
    first = layout_timeline(
        model,
        identity_map,
        scope,
        layout="time-scaled",
        max_objects_per_page=24,
    )
    second = layout_timeline(
        model,
        identity_map,
        scope,
        layout="time-scaled",
        max_objects_per_page=24,
    )

    assert first == second
    assert len(first) == 3
    refs = [item.display_id for item in _primary_clips(first)]
    expected = [identity_map.lookup_semantic("clip", clip.clip_id) for clip in model.clips]
    assert refs == expected
    assert len(refs) == len(set(refs)) == 60
    assert all(len(_primary_clips((page,))) <= 24 for page in first)
    assert all(page.continuation for page in first)


def _schema_registry() -> Registry:
    documents = [json.loads(DEFS_PATH.read_text(encoding="utf-8"))]
    documents.extend(schema.load() for schema in SCHEMAS.values())
    return Registry().with_resources(
        [(document["$id"], Resource.from_contents(document)) for document in documents]
    )


def test_view_map_serialization_is_schema_exact_and_records_omissions(desert) -> None:
    model, identity_map, snapshot, scope = desert
    pages = layout_timeline(model, identity_map, scope, layout="time-scaled")
    result = serialize_view_map(
        pages,
        identity_map=identity_map,
        scope_ref=pages[0].scope_ref,
        snapshot=snapshot,
    )

    errors = sorted(
        Draft202012Validator(
            SCHEMAS["view-map"].load(),
            registry=_schema_registry(),
        ).iter_errors(result),
        key=str,
    )
    assert not errors, "; ".join(error.message for error in errors)
    assert result["reading_order"] == ["PG001", "PG002"]
    for page in result["pages"]:
        assert page["reading_order"] == [
            item["object_ref"] for item in page["object_boxes"]
        ]
    omitted = [
        label
        for page in result["pages"]
        for label in page["labels"]
        if label["status"] == "omitted"
    ]
    assert omitted
    assert all(label["reason"] and label["bbox"] is None for label in omitted)
    layout_ruler_labels = [
        item
        for page in pages
        for item in page.objects
        if item.kind == "label"
        and item.label
        and item.label.partition("fr · ")[0].isdigit()
    ]
    view_map_ruler_labels = [
        label
        for page in result["pages"]
        for label in page["labels"]
        if label["text"].partition("fr · ")[0].isdigit()
    ]
    assert view_map_ruler_labels == [
        {
            "object_ref": item.display_id,
            "text": item.label,
            "status": "printed",
            "reason": None,
            "bbox": {
                "x": item.box.x,
                "y": item.box.y,
                "width": item.box.w,
                "height": item.box.h,
            },
        }
        for item in layout_ruler_labels
    ]
    assert all(
        page.reading_order == tuple(item.display_id for item in page.objects)
        for page in pages
    )


def test_layout_is_deeply_deterministic(desert) -> None:
    model, identity_map, _snapshot, scope = desert
    assert layout_timeline(
        model,
        identity_map,
        scope,
        layout="time-scaled",
    ) == layout_timeline(
        model,
        identity_map,
        scope,
        layout="time-scaled",
    )
    assert layout_timeline(model, identity_map, scope, layout="linear") == layout_timeline(
        model,
        identity_map,
        scope,
        layout="linear",
    )


def test_range_scope_uses_requested_window_without_compressing_tail(desert) -> None:
    model, identity_map, _snapshot, _scope = desert
    scope = select_scope(
        model,
        kind="range",
        ref="late-tail",
        start=97.0,
        end=120.0,
    )
    pages = layout_timeline(model, identity_map, scope, layout="time-scaled")

    assert len(pages) == 1
    assert pages[0].scope_ref == "TL01.RG01"
    assert pages[0].scope_bounds_frames == (2328, 2880)
    audio = _primary_clips(pages)[0]
    assert audio.display_id == identity_map.lookup_semantic("clip", "toccata-fugue")
    # Only [2328,2352) is visible inside the full requested 552-frame window.
    assert audio.box.w / 1600.0 == pytest.approx(24 / 552)
    assert not any(
        item.kind == "label"
        and item.label
        and item.label.startswith("visual detail ends")
        for item in pages[0].objects
    )
