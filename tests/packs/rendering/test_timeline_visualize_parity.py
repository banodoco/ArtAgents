"""Parity contract for the pinned timeline-composition v0.0.6 behavior."""

from __future__ import annotations

import json
import runpy
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

# The canonical schema is an optional external package. Keep this module
# collectible in a clean Astrid install so the independent compositor parity
# tests still run; only the exact canonical-schema assertion below needs it.
try:
    from banodoco_timeline_schema import validate_timeline as validate_timeline_schema
except ModuleNotFoundError as exc:  # pragma: no cover - clean-install regression
    if exc.name != "banodoco_timeline_schema":
        raise
    validate_timeline_schema = None

from astrid.core.timeline.duration import (
    clip_end_frame,
    clip_source_duration,
    clip_start_frame,
    clip_timeline_duration,
    resolve_transition_duration_frames,
    timeline_duration_frames,
    timeline_duration_seconds,
    validate_clip_timing,
    visual_tracks_paint_order,
)

TESTS_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_ROOT / "fixtures" / "timeline_visualize"
PARITY_ROOT = FIXTURE_ROOT / "compositor_parity"
REFERENCE_ROOT = TESTS_ROOT.parent / "docs" / "reference" / "timeline-composition-v0.0.6"


def _fixture_number(path: Path) -> int:
    return int(path.stem.split("_", 1)[0][1:])


FIXTURE_PATHS = sorted(PARITY_ROOT.glob("F*.json"), key=_fixture_number)
EXPECTED = json.loads((PARITY_ROOT / "expected.json").read_text())["fixtures"]
ORACLE = runpy.run_path(str(PARITY_ROOT / "oracle.py"))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _fps(timeline: dict[str, Any]) -> int:
    return int(timeline["theme_overrides"]["visual"]["canvas"]["fps"])


def _normalize_facts(facts: dict[str, Any]) -> dict[str, Any]:
    clips = {
        clip_id: {
            **clip_facts,
            "source_seconds": round(clip_facts["source_seconds"], 4),
            "timeline_seconds": round(clip_facts["timeline_seconds"], 4),
        }
        for clip_id, clip_facts in facts["clips"].items()
    }
    return {
        "clips": clips,
        "timeline_frames": facts["timeline_frames"],
        "timeline_seconds": round(facts["timeline_seconds"], 4),
    }


def _production_facts(timeline: dict[str, Any], fps: int) -> dict[str, Any]:
    clips: dict[str, dict[str, float | int]] = {}
    for clip in timeline["clips"]:
        validate_clip_timing(clip)
        start = clip_start_frame(clip, fps)
        end = clip_end_frame(clip, fps)
        clips[clip["id"]] = {
            "source_seconds": clip_source_duration(clip),
            "timeline_seconds": clip_timeline_duration(clip),
            "start_frame": start,
            "duration_frames": end - start,
            "end_frame": end,
        }
    return {
        "clips": clips,
        "timeline_frames": timeline_duration_frames(timeline, fps),
        "timeline_seconds": timeline_duration_seconds(timeline, fps),
    }


def _expected_core(expected: dict[str, Any]) -> dict[str, Any]:
    return {
        "clips": expected["clips"],
        "timeline_frames": expected["timeline_frames"],
        "timeline_seconds": expected["timeline_seconds"],
    }


VALID_PATHS = [path for path in FIXTURE_PATHS if not path.stem.startswith("F9_")]


def test_fixture_manifest_is_complete() -> None:
    assert len(FIXTURE_PATHS) == 10
    assert {path.stem for path in FIXTURE_PATHS} == set(EXPECTED)


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda path: path.stem)
def test_fixture_is_valid_against_canonical_timeline_schema(fixture_path: Path) -> None:
    if validate_timeline_schema is None:
        pytest.skip(
            "optional banodoco_timeline_schema is unavailable; install the external "
            "package with `python -m pip install -e "
            "/path/to/banodoco-workspace/packages/timeline-schema/python`"
        )
    validate_timeline_schema(_load(fixture_path), strict=True)


@pytest.mark.parametrize("fixture_path", VALID_PATHS, ids=lambda path: path.stem)
def test_production_matches_independent_oracle_and_expected(fixture_path: Path) -> None:
    timeline = _load(fixture_path)
    expected = EXPECTED[fixture_path.stem]
    fps = _fps(timeline)
    assert fps == expected["fps"]

    production = _normalize_facts(_production_facts(timeline, fps))
    oracle = _normalize_facts(ORACLE["timeline_facts"](timeline, fps))
    assert production == oracle == _expected_core(expected)


def _transition_resolution_name(transition: Any, registered_default: int | None) -> str:
    if isinstance(transition, dict) and transition.get("durationFrames") is not None:
        return "explicit_frames"
    if isinstance(transition, dict) and transition.get("duration") is not None:
        return "duration_seconds"
    if registered_default is not None:
        return "registered_default"
    return "hard_fallback"


def _transition_schedule(
    timeline: dict[str, Any], expected: dict[str, Any]
) -> list[dict[str, Any]]:
    fps = _fps(timeline)
    composition_frames = timeline_duration_frames(timeline, fps)
    by_track: defaultdict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for source_index, clip in enumerate(timeline["clips"]):
        by_track[clip["track"]].append((source_index, clip))

    cases: list[dict[str, Any]] = []
    track_ids = [track["id"] for track in timeline["tracks"] if track["kind"] == "visual"]
    for track_id in track_ids:
        clips = [
            item[1]
            for item in sorted(by_track[track_id], key=lambda item: (item[1]["at"], item[0]))
        ]
        index = 0
        while index < len(clips):
            from_clip = clips[index]
            transition = from_clip.get("transition")
            if not transition:
                index += 1
                continue

            transition_id = (
                transition
                if isinstance(transition, str)
                else transition.get("id", transition.get("type"))
            )
            assert transition_id == "cross-fade"
            to_clip = clips[index + 1] if index + 1 < len(clips) else None
            if to_clip is None:
                cases.append({"from_id": from_clip["id"], "to_id": None, "ignored": "last_clip"})
                index += 1
                continue
            if (
                from_clip.get("clipType") == "effect-layer"
                or to_clip.get("clipType") == "effect-layer"
            ):
                cases.append(
                    {"from_id": from_clip["id"], "to_id": to_clip["id"], "ignored": "effect_layer"}
                )
                index += 1
                continue

            from_start = clip_start_frame(from_clip, fps)
            from_end = clip_end_frame(from_clip, fps)
            to_start = clip_start_frame(to_clip, fps)
            if to_start < from_start or to_start > from_end:
                cases.append(
                    {
                        "from_id": from_clip["id"],
                        "to_id": to_clip["id"],
                        "ignored": "outside_current_span",
                    }
                )
                index += 1
                continue

            from_duration = from_end - from_start
            to_duration = clip_end_frame(to_clip, fps) - to_start
            registered_default = expected["transition_defaults"][from_clip["id"]]
            resolved = resolve_transition_duration_frames(
                transition,
                from_duration,
                to_duration,
                registered_default,
                fps=fps,
            )
            if resolved is None:
                cases.append(
                    {
                        "from_id": from_clip["id"],
                        "to_id": to_clip["id"],
                        "ignored": "duration_bounds",
                    }
                )
                index += 1
                continue

            to_offset = max(0, from_duration - resolved)
            group_duration = to_offset + to_duration
            group_end = from_start + group_duration
            cases.append(
                {
                    "from_id": from_clip["id"],
                    "to_id": to_clip["id"],
                    "resolution": _transition_resolution_name(transition, registered_default),
                    "duration_frames": resolved,
                    "group_start_frame": from_start,
                    "to_offset_frame": to_offset,
                    "group_duration_frames": group_duration,
                    "group_end_frame": group_end,
                    "visible_end_frame": min(group_end, composition_frames),
                }
            )
            index += 2
    return cases


@pytest.mark.parametrize(
    "fixture_name",
    ["F7_transition_bounds", "F10_transition-last-clip-ignored"],
)
def test_transition_pairing_precedence_and_bounds(fixture_name: str) -> None:
    timeline = _load(PARITY_ROOT / f"{fixture_name}.json")
    expected = EXPECTED[fixture_name]
    assert _transition_schedule(timeline, expected) == expected["transition_cases"]

    prompted_layers = [clip for clip in timeline["clips"] if clip.get("clipType") == "effect-layer"]
    for clip in prompted_layers:
        assert clip["generation"]["prompt"].strip()


def test_visual_tracks_are_painted_in_reverse_config_order() -> None:
    timeline = _load(PARITY_ROOT / "F8_z_order.json")
    expected = EXPECTED["F8_z_order"]
    config_order = [track["id"] for track in timeline["tracks"] if track["kind"] == "visual"]
    paint_order = visual_tracks_paint_order(timeline["tracks"])
    assert config_order == expected["visual_config_order"]
    assert paint_order == expected["visual_paint_order"]
    assert paint_order[-1] == expected["topmost_track"]


def test_zero_and_negative_speed_fixture_is_rejected_before_arithmetic() -> None:
    fixture_name = "F9_speed-zero-rejected"
    timeline = _load(PARITY_ROOT / f"{fixture_name}.json")
    expected = EXPECTED[fixture_name]
    assert [clip["id"] for clip in timeline["clips"]] == expected["rejected_clip_ids"]
    for clip in timeline["clips"]:
        with pytest.raises(ValueError, match=expected["error"]):
            validate_clip_timing(clip)
    with pytest.raises(ValueError, match=expected["error"]):
        timeline_duration_frames(timeline, expected["fps"])


@pytest.mark.parametrize("bad_speed", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_speed_is_rejected(bad_speed: float) -> None:
    with pytest.raises(ValueError, match="clip.speed must be finite"):
        validate_clip_timing({"id": "bad", "at": 0, "hold": 1, "speed": bad_speed})


@pytest.mark.parametrize(
    ("clip", "message"),
    [
        ({"at": "now", "hold": 1}, "clip.at must be a number"),
        ({"at": 0, "from": "start", "to": 1}, "clip.from must be a number"),
        ({"at": 0, "from": 0, "to": "end"}, "clip.to must be a number"),
        ({"at": 0, "from": 2, "to": 1}, "clip.from must not be greater"),
        ({"at": 0, "hold": -0.1}, "clip.hold must not be negative"),
    ],
)
def test_other_invalid_timing_is_rejected(clip: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_clip_timing(clip)


def test_positive_fractional_speed_is_not_clamped() -> None:
    clip = {"id": "slow", "at": 0, "hold": 1, "speed": 0.5}
    validate_clip_timing(clip)
    assert clip_timeline_duration(clip) == 2.0


def test_numeric_hold_bypasses_reversed_trim_bounds_in_production_and_oracle() -> None:
    fps = 30
    clip = {"id": "hold-wins", "at": 0, "hold": 2, "from": 5, "to": 1}

    validate_clip_timing(clip)
    production = {
        "source_seconds": clip_source_duration(clip),
        "timeline_seconds": clip_timeline_duration(clip),
        "start_frame": clip_start_frame(clip, fps),
        "duration_frames": clip_end_frame(clip, fps) - clip_start_frame(clip, fps),
        "end_frame": clip_end_frame(clip, fps),
    }

    assert production == ORACLE["clip_facts"](clip, fps)
    assert production["source_seconds"] == 2
    assert production["timeline_seconds"] == 2
    assert timeline_duration_seconds({"clips": [clip]}, fps) == 2
    assert production["end_frame"] == max(1, round(2 * fps))


def test_empty_timeline_keeps_the_compositor_one_frame_floor() -> None:
    assert timeline_duration_frames({"clips": []}, 30) == 1
    assert round(timeline_duration_seconds({"clips": []}, 30), 4) == 0.0333


def test_seconds_transition_requires_explicit_fps_context() -> None:
    transition = {"id": "cross-fade", "duration": 0.4}
    with pytest.raises(ValueError, match="fps is required"):
        resolve_transition_duration_frames(transition, 90, 90, 8)


def test_desert_frozen_facts_are_reproduced_without_project_files() -> None:
    truth = _load(FIXTURE_ROOT / "desert_truth.json")
    desert_slice = _load(FIXTURE_ROOT / "desert_slice" / "clips_tracks.json")
    fps = truth["fps"]
    track_kinds = {track["id"]: track["kind"] for track in desert_slice["tracks"]}
    visual_clips = [
        clip for clip in desert_slice["clips"] if track_kinds[clip["track"]] == "visual"
    ]
    [audio_clip] = [
        clip for clip in desert_slice["clips"] if track_kinds[clip["track"]] == "audio"
    ]

    authored_visual_end = max(clip["at"] + clip_source_duration(clip) for clip in visual_clips)
    visual_timeline = {"clips": visual_clips}
    all_track_timeline = {"clips": desert_slice["clips"]}

    assert desert_slice["fps"] == fps
    assert audio_clip["track"] == "4a47c8fd-2287-4808-89b0-73f956a66eac"
    assert round(authored_visual_end, 4) == truth["durations_seconds"]["authored_visual_only_end"]
    assert timeline_duration_frames(visual_timeline, fps) == truth["durations_frames"][
        "frame_quantized_visual"
    ]
    assert round(timeline_duration_seconds(visual_timeline, fps), 4) == truth["durations_seconds"][
        "frame_quantized_visual_end"
    ]
    assert timeline_duration_frames(all_track_timeline, fps) == truth["durations_frames"][
        "all_track_composition"
    ]
    assert timeline_duration_seconds(all_track_timeline, fps) == truth["durations_seconds"][
        "all_track_composition_end"
    ]


def test_pinned_source_snapshot_is_self_contained() -> None:
    source_files = [
        path for path in REFERENCE_ROOT.rglob("*") if path.suffix in {".ts", ".tsx"}
    ]
    assert len(source_files) == 20
    assert (REFERENCE_ROOT / "lib" / "duration.ts").is_file()
    assert (REFERENCE_ROOT / "lib" / "transitions.tsx").is_file()
    readme = (REFERENCE_ROOT / "README.md").read_text()
    assert "v0.0.6" in readme
    assert (
        "https://github.com/banodoco/timeline-composition/archive/refs/tags/v0.0.6.tar.gz"
        in readme
    )
