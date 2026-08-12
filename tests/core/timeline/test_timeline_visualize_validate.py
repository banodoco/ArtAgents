from __future__ import annotations

import math
from typing import Any

import pytest

from astrid.packs.rendering.executors.timeline_visualize import validate_structural


def _timeline(*clips: dict[str, Any]) -> dict[str, Any]:
    return {
        "tracks": [{"id": "v1", "kind": "visual", "label": "V1"}],
        "clips": list(clips),
    }


def _clip(**overrides: Any) -> dict[str, Any]:
    return {"id": "c1", "track": "v1", "at": 0, "hold": 1, **overrides}


def test_duplicate_track_id_is_reported() -> None:
    timeline = _timeline()
    timeline["tracks"].append({"id": "v1", "kind": "audio", "label": "A1"})
    assert validate_structural(timeline) == ["duplicate track id 'v1'"]


def test_duplicate_clip_id_is_reported() -> None:
    assert validate_structural(_timeline(_clip(), _clip(at=1))) == [
        "duplicate clip id 'c1'"
    ]


def test_dangling_track_reference_is_reported() -> None:
    assert validate_structural(_timeline(_clip(track="missing"))) == [
        "clip 'c1' references nonexistent track 'missing'"
    ]


@pytest.mark.parametrize("speed", [0, -1])
def test_non_positive_speed_is_reported(speed: float) -> None:
    assert validate_structural(_timeline(_clip(speed=speed))) == [
        "clip 'c1': clip.speed must be positive"
    ]


@pytest.mark.parametrize("speed", [math.nan, math.inf, -math.inf])
def test_non_finite_speed_is_reported(speed: float) -> None:
    assert validate_structural(_timeline(_clip(speed=speed))) == [
        "clip 'c1': clip.speed must be finite"
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"at": "now"}, "clip.at must be a number"),
        ({"hold": None, "from": "start", "to": 1}, "clip.from must be a number"),
        ({"hold": None, "from": 0, "to": "end"}, "clip.to must be a number"),
    ],
)
def test_non_numeric_timing_field_is_reported(
    overrides: dict[str, Any], message: str
) -> None:
    assert validate_structural(_timeline(_clip(**overrides))) == [f"clip 'c1': {message}"]


def test_reversed_trim_without_hold_is_reported() -> None:
    errors = validate_structural(_timeline(_clip(hold=None, **{"from": 5, "to": 1})))
    assert errors == ["clip 'c1': clip.from must not be greater than clip.to"]


def test_reversed_trim_with_numeric_hold_passes() -> None:
    assert validate_structural(_timeline(_clip(hold=2, **{"from": 5, "to": 1}))) == []


def test_negative_hold_is_reported() -> None:
    assert validate_structural(_timeline(_clip(hold=-1))) == [
        "clip 'c1': clip.hold must not be negative"
    ]
