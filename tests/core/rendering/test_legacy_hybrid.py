from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from astrid.core.rendering.contracts import RenderPlan, RenderRequest, SupportReport
from astrid.core.rendering.errors import RendererUnsupportedError
from astrid.core.rendering.registry import load_default_registries
from astrid.core.rendering.transport import CommandTransport
from astrid.packs.rendering.planners.legacy_hybrid import run as legacy_hybrid


def _timeline(*, clips: list[dict] | None = None, fps: int | list[int] = 30) -> dict:
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": fps}}
        },
        "tracks": [
            {"id": "v", "kind": "visual"},
            {"id": "a", "kind": "audio"},
        ],
        "clips": clips or [],
    }


def _media(
    clip_id: str = "media",
    *,
    at: float = 0,
    duration: float = 4,
    track: str = "v",
    **extra: object,
) -> dict:
    return {
        "id": clip_id,
        "at": at,
        "track": track,
        "clipType": "media",
        "asset": "source",
        "from": 0,
        "to": duration,
        "speed": 1,
        "volume": 0,
        **extra,
    }


def _request(tmp_path: Path, timeline: dict, *, config: dict | None = None) -> RenderRequest:
    timeline_path = tmp_path / "timeline.json"
    assets_path = tmp_path / "assets.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    assets_path.write_text(json.dumps({"assets": {}}), encoding="utf-8")
    return RenderRequest(
        schema_version=1,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name="video.mp4",
        backend_config=(
            {} if config is None else {legacy_hybrid.BACKEND_ID: config}
        ),
    )


def _resolver(
    supported: set[str] | None = None,
):
    accepted = (
        {
            legacy_hybrid.FFMPEG_ID,
            legacy_hybrid.REMOTION_ID,
            "raw_command.renderer",
        }
        if supported is None
        else supported
    )

    def resolve(
        renderer_id: str, _request: RenderRequest, _timeline: object
    ) -> SupportReport:
        ok = renderer_id in accepted
        return SupportReport(
            schema_version=1,
            supported=ok,
            reasons=[] if ok else ["fixture rejection"],
            features={"fixture": True},
            alternatives=[],
            backend=renderer_id,
            backend_version=None,
        )

    return resolve


def _plan(tmp_path: Path, timeline: dict, *, config: dict | None = None) -> RenderPlan:
    return legacy_hybrid.plan(
        _request(tmp_path, timeline, config=config),
        workspace=tmp_path,
        support_resolver=_resolver(),
    )


def test_empty_plan_is_valid_zero_frame_plan(tmp_path: Path) -> None:
    result = _plan(tmp_path, _timeline())

    assert result.total_frames == 0
    assert result.segments == []
    assert result.reasons == {}
    assert result.window is None
    assert result.finalizer.id == "rendering.ffmpeg-finalizer"


def test_single_segment_uses_supported_qualified_renderer(tmp_path: Path) -> None:
    result = _plan(tmp_path, _timeline(clips=[_media(duration=2)]))

    assert [(item.window.start_frame, item.window.end_frame) for item in result.segments] == [
        (0, 60)
    ]
    assert result.segments[0].renderer.id == "rendering.ffmpeg"
    assert result.segments[0].renderer.support_decision.supported is True
    assert result.profile.fps_rational == (30, 1)


def test_multiple_segments_tile_the_timeline_exactly(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=10),
            {
                "id": "title",
                "at": 4,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ]
    )
    result = _plan(tmp_path, timeline)

    windows = [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ]
    assert windows == [
        (0, 112, "rendering.ffmpeg"),
        (112, 158, "rendering.remotion"),
        (158, 300, "rendering.ffmpeg"),
    ]
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))


def test_all_ffmpeg_hybrid(tmp_path: Path) -> None:
    result = _plan(
        tmp_path,
        _timeline(clips=[_media(duration=3)]),
        config={"renderers": ["rendering.ffmpeg"]},
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "rendering.ffmpeg"
    ]


def test_mixed_raw_fixture_and_builtin_plan(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=6),
            {
                "id": "builtin-title",
                "at": 2,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ]
    )
    result = _plan(
        tmp_path,
        timeline,
        config={
            "simple_renderers": ["raw_command.renderer"],
            "complex_renderers": ["rendering.remotion"],
        },
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]


def test_frame_rounding_is_integer_and_exactly_tiles(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=2.01),
            {
                "id": "card",
                "at": 0.5,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ],
        fps=[30000, 1001],
    )
    result = _plan(tmp_path, timeline)

    assert result.total_frames == 61
    assert all(type(value) is int for segment in result.segments for value in (
        segment.window.start_frame,
        segment.window.end_frame,
    ))
    assert result.segments[0].window.start_frame == 0
    assert result.segments[-1].window.end_frame == result.total_frames
    assert all(
        left.window.end_frame == right.window.start_frame
        for left, right in zip(result.segments, result.segments[1:])
    )


@pytest.mark.parametrize(
    ("transition", "expected"),
    [
        ({"type": "crossfade"}, (44, 76)),
        ({"duration": 0.5, "durationFrames": 12}, (37, 83)),
        ({"durationFrames": 12}, (40, 80)),
    ],
)
def test_transition_units_and_handles_are_preserved(
    transition: dict, expected: tuple[int, int]
) -> None:
    timeline = _timeline(
        clips=[
            _media("left", duration=2, transition=transition),
            _media("right", at=2, duration=2),
        ]
    )

    assert legacy_hybrid._complex_frame_windows(
        timeline, Fraction(30, 1)
    ) == [expected]


def test_support_rejects_speed_and_overlapping_audio(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=4),
            _media("fast", at=0, duration=2, speed=2),
            _media("audio-a", at=0, duration=2, track="a"),
            _media("audio-b", at=1, duration=2, track="a"),
        ]
    )
    report = legacy_hybrid.support(
        _request(tmp_path, timeline), workspace=tmp_path
    )

    assert report.supported is False
    assert any("speed" in reason for reason in report.reasons)
    assert any("Overlapping audio" in reason for reason in report.reasons)
    with pytest.raises(RendererUnsupportedError):
        legacy_hybrid.plan(
            _request(tmp_path, timeline),
            workspace=tmp_path,
            support_resolver=_resolver(),
        )


def test_raw_support_adapter_and_registered_protocol(tmp_path: Path) -> None:
    request = _request(tmp_path, _timeline(clips=[_media(duration=1)]))
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
    report = CommandTransport(legacy_hybrid.BACKEND_ID).run(
        "support",
        ["python3", "run.py"],
        request_path=request_path,
        result_path=result_path,
        cwd=Path(legacy_hybrid.__file__).resolve().parents[2],
    )

    assert isinstance(report, SupportReport)
    assert report.supported is True
    renderers, planners, finalizers = load_default_registries(
        Path(__file__).resolve().parents[3], include_installed=False
    )
    assert renderers.get("rendering.ffmpeg").id == "rendering.ffmpeg"
    assert planners.get(legacy_hybrid.BACKEND_ID).manifest.operations == (
        "plan",
        "support",
    )
    assert finalizers.get("rendering.ffmpeg-finalizer").id == (
        "rendering.ffmpeg-finalizer"
    )


def test_assignment_failure_is_structured_and_leaves_no_segment_artifacts(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, _timeline(clips=[_media(duration=1)]))
    with pytest.raises(RendererUnsupportedError) as caught:
        legacy_hybrid.plan(
            request,
            workspace=tmp_path,
            support_resolver=_resolver(set()),
        )

    assert caught.value.error.kind == "unsupported"
    assert not list(tmp_path.rglob("segment-*.mp4"))
    assert not list(tmp_path.glob("*.provenance.json"))


def test_segment_order_is_provenance_alignment_order(tmp_path: Path) -> None:
    result = _plan(
        tmp_path,
        _timeline(
            clips=[
                _media(duration=5),
                {
                    "id": "card",
                    "at": 2,
                    "track": "v",
                    "clipType": "text-card",
                    "hold": 1,
                },
            ]
        ),
    )
    payload = RenderPlan.from_dict(result.to_dict()).to_dict()

    assert [segment["renderer"]["id"] for segment in payload["segments"]] == [
        "rendering.ffmpeg",
        "rendering.remotion",
        "rendering.ffmpeg",
    ]
    assert list(payload["reasons"]) == ["0", "1", "2"]


# ---------------------------------------------------------------------------
# T4.5 — planner routing / hybrid matrix
# ---------------------------------------------------------------------------


def _complex_timeline() -> dict:
    """Media plus an overlapping text-card: simple/complex/simple windows."""
    return _timeline(
        clips=[
            _media(duration=6),
            {
                "id": "title",
                "at": 2,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ]
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        # Defaults: ffmpeg for simple windows, remotion for complex.
        (
            None,
            ["rendering.ffmpeg", "rendering.remotion", "rendering.ffmpeg"],
        ),
        # A common renderers list applies to every window kind.
        (
            {"renderers": ["rendering.remotion"]},
            ["rendering.remotion", "rendering.remotion", "rendering.remotion"],
        ),
        # The raw fixture (Batch 2) is a simple renderer; remotion owns complex.
        (
            {
                "simple_renderers": ["raw_command.renderer"],
                "complex_renderers": ["rendering.remotion"],
            },
            ["raw_command.renderer", "rendering.remotion", "raw_command.renderer"],
        ),
        # First supported renderer in a list wins per window kind.
        (
            {
                "simple_renderers": ["rendering.ffmpeg", "raw_command.renderer"],
                "complex_renderers": ["rendering.remotion"],
            },
            ["rendering.ffmpeg", "rendering.remotion", "rendering.ffmpeg"],
        ),
    ],
    ids=[
        "defaults",
        "common-renderers",
        "raw-simple-remotion-complex",
        "first-supported-wins",
    ],
)
def test_planner_renderer_assignment_matrix(
    tmp_path: Path, config: dict | None, expected: list[str]
) -> None:
    result = _plan(tmp_path, _complex_timeline(), config=config)

    assert [segment.renderer.id for segment in result.segments] == expected
    windows = [
        (segment.window.start_frame, segment.window.end_frame)
        for segment in result.segments
    ]
    assert windows[0][0] == 0
    assert windows[-1][1] == result.total_frames
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))
    assert all(
        segment.renderer.support_decision.supported is True
        for segment in result.segments
    )
    assert result.finalizer.id == "rendering.ffmpeg-finalizer"


def test_planner_falls_back_to_next_supported_simple_renderer(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        _timeline(clips=[_media(duration=2)]),
        config={
            "simple_renderers": ["rendering.ffmpeg", "raw_command.renderer"]
        },
    )
    result = legacy_hybrid.plan(
        request,
        workspace=tmp_path,
        support_resolver=_resolver(supported={"raw_command.renderer"}),
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "raw_command.renderer"
    ]


def test_planner_falls_back_to_next_supported_complex_renderer(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        _complex_timeline(),
        config={
            "simple_renderers": ["rendering.ffmpeg"],
            "complex_renderers": ["rendering.remotion", "rendering.ffmpeg"],
        },
    )
    result = legacy_hybrid.plan(
        request,
        workspace=tmp_path,
        support_resolver=_resolver(
            supported={"rendering.ffmpeg", "raw_command.renderer"}
        ),
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "rendering.ffmpeg",
        "rendering.ffmpeg",
        "rendering.ffmpeg",
    ]


def test_planner_rejects_unknown_config_keys(tmp_path: Path) -> None:
    with pytest.raises(RendererUnsupportedError) as caught:
        _plan(tmp_path, _complex_timeline(), config={"bogus": True})

    assert "unknown rendering.legacy_hybrid configuration: bogus" in (
        caught.value.error.details["reasons"]
    )


def test_planner_rejects_empty_renderer_lists(tmp_path: Path) -> None:
    with pytest.raises(RendererUnsupportedError) as caught:
        _plan(tmp_path, _complex_timeline(), config={"renderers": []})
    assert "renderers must not be empty" in caught.value.error.details["reasons"]

    with pytest.raises(RendererUnsupportedError) as caught:
        _plan(
            tmp_path,
            _complex_timeline(),
            config={"simple_renderers": [], "complex_renderers": []},
        )
    assert "simple_renderers must not be empty" in caught.value.error.details["reasons"]


def test_planner_single_segment_is_one_full_timeline_window(
    tmp_path: Path,
) -> None:
    result = _plan(tmp_path, _timeline(clips=[_media(duration=3)]))

    assert len(result.segments) == 1
    segment = result.segments[0]
    assert (segment.window.start_frame, segment.window.end_frame) == (
        0,
        result.total_frames,
    )
    assert result.reasons == {"0": "simple legacy window assigned to rendering.ffmpeg by supported report"}
    assert result.window is None
