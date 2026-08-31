from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from astrid.core.rendering.contracts import RenderPlan, RenderRequest, SupportReport
from astrid.core.rendering.errors import RendererUnsupportedError
from astrid.core.rendering.registry import load_default_registries
from astrid.core.rendering.transport import CommandTransport
from astrid.packs.rendering.planners.threejs_hybrid import run as hybrid
from astrid.sdk.rendering import render
from tests.packs.rendering._helpers import _execution_env, _frame_md5, _probe, _source_video

MIXED_CANVAS = {"width": 320, "height": 180, "fps": 24}


def _timeline(
    *,
    clips: list[dict] | None = None,
    fps: int | list[int] = 30,
    tracks: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    result: dict = {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": fps}}
        },
        "tracks": tracks
        or [
            {"id": "v", "kind": "visual"},
            {"id": "a", "kind": "audio"},
        ],
        "clips": clips or [],
    }
    if metadata is not None:
        result["metadata"] = metadata
    return result


def _text(
    clip_id: str = "title",
    *,
    at: float = 0,
    hold: float = 1,
    track: str = "v",
    **extra: object,
) -> dict:
    return {
        "id": clip_id,
        "at": at,
        "track": track,
        "clipType": "text",
        "text": {
            "content": "Hello",
            "fontSize": 48,
            "color": "#ffffff",
            "align": "center",
            "bold": False,
        },
        "params": {
            "anchor": "center",
            "offsetX": 0,
            "offsetY": 0,
            "textShadow": False,
            "maxWidth": 100,
            "weight": 400,
        },
        "hold": hold,
        **extra,
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
            {} if config is None else {hybrid.BACKEND_ID: config}
        ),
    )


def _resolver(
    supported: set[str] | None = None,
):
    accepted = (
        {hybrid.THREE_ID, hybrid.REMOTION_ID}
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
    renderers, _planners, finalizers = load_default_registries(
        Path(__file__).resolve().parents[3]
    )
    return hybrid.plan(
        _request(tmp_path, timeline, config=config),
        workspace=tmp_path,
        support_resolver=_resolver(),
        registries=(renderers, finalizers),
    )


def _assert_exact_tiling(result: RenderPlan) -> None:
    """Exact half-open tiling: no gaps, overlaps, zero-length segments, or
    recursive planner ids; identity and finalizer pinned on every segment."""

    windows = [
        (segment.window.start_frame, segment.window.end_frame, segment.renderer.id)
        for segment in result.segments
    ]
    assert windows[0][0] == 0
    assert windows[-1][1] == result.total_frames
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))
    assert all(end > start for start, end, _renderer in windows)
    assert all(
        renderer_id in {hybrid.THREE_ID, hybrid.REMOTION_ID}
        for _start, _end, renderer_id in windows
    )
    assert all(
        segment.renderer.support_decision.backend == segment.renderer.id
        for segment in result.segments
    )
    assert all(
        segment.renderer.support_decision.supported is True
        for segment in result.segments
    )
    assert result.finalizer.id == hybrid.FINALIZER_ID


# ---------------------------------------------------------------------------
# Classification and exact windows
# ---------------------------------------------------------------------------


def test_text_only_timeline_is_one_three_segment(tmp_path: Path) -> None:
    result = _plan(tmp_path, _timeline(clips=[_text(at=0, hold=2)]))

    assert result.total_frames == 60
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [(0, 60, hybrid.THREE_ID)]
    assert result.profile.fps_rational == (30, 1)
    _assert_exact_tiling(result)


def test_media_anywhere_falls_back_to_remotion(tmp_path: Path) -> None:
    result = _plan(tmp_path, _timeline(clips=[_media(duration=2)]))

    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [(0, 60, hybrid.REMOTION_ID)]
    _assert_exact_tiling(result)


def test_text_media_text_tiles_three_remotion_three(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _text("t1", at=0, hold=2),
            _media("m", at=3, duration=1),
            _text("t2", at=4.5, hold=1),
        ]
    )
    result = _plan(tmp_path, timeline)

    assert result.total_frames == 165
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [
        (0, 60, hybrid.THREE_ID),
        (60, 135, hybrid.REMOTION_ID),
        (135, 165, hybrid.THREE_ID),
    ]
    _assert_exact_tiling(result)


def test_text_overlapping_media_merges_into_one_remotion_component(
    tmp_path: Path,
) -> None:
    timeline = _timeline(
        clips=[
            _text(at=0, hold=2),
            _media(at=1.5, duration=1),
        ]
    )
    result = _plan(tmp_path, timeline)

    # The overlap is never split: the whole connected component is Remotion.
    assert result.total_frames == 75
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [(0, 75, hybrid.REMOTION_ID)]
    _assert_exact_tiling(result)


@pytest.mark.parametrize(
    ("clip", "label"),
    [
        pytest.param(_text(at=0, hold=2, effects=[{"id": "fx"}]), "effects"),
        pytest.param(_text(at=0, hold=2, transition={"type": "crossfade"}), "transition"),
        pytest.param(_media(at=0, duration=2, track="v2"), "non-base-visual-track"),
        pytest.param(_text(at=0, hold=2, opacity=0.5), "opacity"),
        pytest.param(_media(at=0, duration=2, params={"fadeIn": 0.5}), "audio-fades"),
    ],
    ids=["effects", "transition", "non-base-visual-track", "opacity", "audio-fades"],
)
def test_fallback_classes_route_to_remotion(
    tmp_path: Path, clip: dict, label: str
) -> None:
    tracks = [
        {"id": "v", "kind": "visual"},
        {"id": "v2", "kind": "visual"},
        {"id": "a", "kind": "audio"},
    ]
    timeline = _timeline(clips=[clip], tracks=tracks)
    result = _plan(tmp_path, timeline)

    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [(0, 60, hybrid.REMOTION_ID)], label
    _assert_exact_tiling(result)


def test_gaps_are_remotion_and_tail_extends_to_total_frames(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _text("t1", at=0, hold=1),
            _text("t2", at=2, hold=1),
        ],
        metadata={"duration_seconds": 4},
    )
    result = _plan(tmp_path, timeline)

    assert result.total_frames == 120
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [
        (0, 30, hybrid.THREE_ID),
        (30, 60, hybrid.REMOTION_ID),
        (60, 90, hybrid.THREE_ID),
        (90, 120, hybrid.REMOTION_ID),
    ]
    _assert_exact_tiling(result)


def test_non_integer_clip_times_round_to_frames(tmp_path: Path) -> None:
    result = _plan(tmp_path, _timeline(clips=[_text(at=0.5, hold=1.5)]))

    assert result.total_frames == 60
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [(0, 15, hybrid.REMOTION_ID), (15, 60, hybrid.THREE_ID)]
    _assert_exact_tiling(result)


def test_quarter_second_handle_is_capped_at_next_occupied_region(
    tmp_path: Path,
) -> None:
    timeline = _timeline(
        clips=[
            _text("t1", at=0, hold=2),
            _media("m", at=3, duration=1),
            _text("t2", at=4.1, hold=1),
        ]
    )
    result = _plan(tmp_path, timeline)

    # Un-capped the media handle would run to frame 128; the next occupied
    # text region starts at 123, so the Remotion window stops there.
    assert result.total_frames == 153
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [
        (0, 60, hybrid.THREE_ID),
        (60, 123, hybrid.REMOTION_ID),
        (123, 153, hybrid.THREE_ID),
    ]
    _assert_exact_tiling(result)


def test_quarter_second_handle_is_capped_at_timeline_boundary(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _text("t1", at=0, hold=2),
            _media("m", at=7, duration=1),
        ]
    )
    result = _plan(tmp_path, timeline)

    # The media handle would run to frame 248; the authoritative total frames
    # cap it at 240, so the final window ends exactly at the boundary.
    assert result.total_frames == 240
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [
        (0, 60, hybrid.THREE_ID),
        (60, 240, hybrid.REMOTION_ID),
    ]
    _assert_exact_tiling(result)


def test_adjacent_same_renderer_windows_coalesce(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _text("t1", at=0, hold=1),
            _text("t2", at=1, hold=1),
        ]
    )
    result = _plan(tmp_path, timeline)

    # Touching text components share an exact boundary and coalesce into one
    # Three window without changing coverage.
    assert len(result.segments) == 1
    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [(0, 60, hybrid.THREE_ID)]
    _assert_exact_tiling(result)


def test_empty_timeline_support_rejects(tmp_path: Path) -> None:
    report = hybrid.support(_request(tmp_path, _timeline()), workspace=tmp_path)

    assert report.supported is False
    assert any("empty timeline" in reason for reason in report.reasons)
    with pytest.raises(RendererUnsupportedError):
        _plan(tmp_path, _timeline())


# ---------------------------------------------------------------------------
# Profile / timescale / evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fps", "expected_time_base"),
    [
        (24, (1, 12288)),
        (30, (1, 15360)),
        ([30000, 1001], (1, 30000)),
    ],
    ids=["fps24", "fps30", "ntsc"],
)
def test_canonical_mp4_time_base(
    tmp_path: Path, fps: int | list[int], expected_time_base: tuple[int, int]
) -> None:
    rate = Fraction(*fps) if isinstance(fps, list) else Fraction(fps, 1)

    assert hybrid._mp4_time_base(rate) == expected_time_base
    result = _plan(tmp_path, _timeline(clips=[_text(at=0, hold=1)], fps=fps))
    assert result.profile.fps_rational == tuple(rate.as_integer_ratio())
    assert result.profile.time_base == expected_time_base
    _assert_exact_tiling(result)


def test_real_support_evidence_and_identity(tmp_path: Path) -> None:
    renderers, _planners, finalizers = load_default_registries(
        Path(__file__).resolve().parents[3]
    )
    timeline = _timeline(
        clips=[
            _text(at=0, hold=1),
            _media(at=2, duration=1),
        ]
    )
    result = _plan(tmp_path, timeline)

    assert [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ] == [
        (0, 30, hybrid.THREE_ID),
        (30, 90, hybrid.REMOTION_ID),
    ]
    for segment in result.segments:
        candidate = renderers.get(segment.renderer.id)
        assert segment.renderer.id in {hybrid.THREE_ID, hybrid.REMOTION_ID}
        assert segment.renderer.support_decision.backend == segment.renderer.id
        assert segment.renderer.support_decision.supported is True
        # Real registry evidence — never fabricated by the planner.
        assert segment.renderer.manifest_digest == candidate.manifest_digest
        assert segment.renderer.source_pack["id"] == candidate.pack_id
        assert segment.renderer.trust_eligibility == candidate.eligibility.to_dict()
    assert result.finalizer.id == hybrid.FINALIZER_ID
    finalizer_candidate = finalizers.get(hybrid.FINALIZER_ID)
    assert result.finalizer.manifest_digest == finalizer_candidate.manifest_digest
    assert result.finalizer.source_pack["id"] == finalizer_candidate.pack_id


def test_support_resolver_rejection_is_structured(tmp_path: Path) -> None:
    renderers, _planners, finalizers = load_default_registries(
        Path(__file__).resolve().parents[3]
    )
    request = _request(tmp_path, _timeline(clips=[_text(at=0, hold=1)]))
    with pytest.raises(RendererUnsupportedError) as caught:
        hybrid.plan(
            request,
            workspace=tmp_path,
            support_resolver=_resolver(supported=set()),
            registries=(renderers, finalizers),
        )

    assert caught.value.error.kind == "unsupported"
    assert not list(tmp_path.rglob("segment-*.mp4"))


# ---------------------------------------------------------------------------
# Pure helper characterization
# ---------------------------------------------------------------------------


def test_merged_components_only_merge_strict_overlaps() -> None:
    assert hybrid._merged_components([(0, 10, 0), (10, 20, 1)]) == [
        (0, 10, [0]),
        (10, 20, [1]),
    ]
    assert hybrid._merged_components([(0, 10, 0), (9, 20, 1), (15, 25, 2)]) == [
        (0, 25, [0, 1, 2])
    ]
    assert hybrid._merged_components([(5, 8, 0), (0, 3, 1), (10, 12, 2)]) == [
        (0, 3, [1]),
        (5, 8, [0]),
        (10, 12, [2]),
    ]


def test_clip_frame_range_rounds_and_keeps_minimum_one_frame() -> None:
    fps = Fraction(30, 1)
    assert hybrid._clip_frame_range(_text(at=0.5, hold=1.5), fps) == (15, 60)
    # A positive sub-frame clip still owns the frame it starts on.
    assert hybrid._clip_frame_range(_text(at=0, hold=0.01), fps) == (0, 1)
    assert hybrid._clip_frame_range(_media(at=1, duration=0.02), fps) == (30, 31)


# ---------------------------------------------------------------------------
# Registration / protocol
# ---------------------------------------------------------------------------


def test_registered_protocol_and_registry_identity(tmp_path: Path) -> None:
    renderers, planners, finalizers = load_default_registries(
        Path(__file__).resolve().parents[3]
    )
    candidate = planners.get(hybrid.BACKEND_ID)
    assert candidate.manifest.operations == ("support", "plan")
    assert renderers.get(hybrid.THREE_ID).id == hybrid.THREE_ID
    assert renderers.get(hybrid.REMOTION_ID).id == hybrid.REMOTION_ID
    assert finalizers.get(hybrid.FINALIZER_ID).id == hybrid.FINALIZER_ID

    request = _request(tmp_path, _timeline(clips=[_text(at=0, hold=1)]))
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
    report = CommandTransport(hybrid.BACKEND_ID).run(
        "support",
        candidate.manifest.command,
        request_path=request_path,
        result_path=result_path,
        cwd=candidate.pack_root,
    )

    assert isinstance(report, SupportReport)
    assert report.supported is True
    assert report.backend == hybrid.BACKEND_ID


def test_registered_protocol_rejects_empty_timeline(tmp_path: Path) -> None:
    _planners_holder = load_default_registries(
        Path(__file__).resolve().parents[3]
    )[1]
    candidate = _planners_holder.get(hybrid.BACKEND_ID)
    request = _request(tmp_path, _timeline())
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
    report = CommandTransport(hybrid.BACKEND_ID).run(
        "support",
        candidate.manifest.command,
        request_path=request_path,
        result_path=result_path,
        cwd=candidate.pack_root,
    )

    assert isinstance(report, SupportReport)
    assert report.supported is False
    assert any("empty timeline" in reason for reason in report.reasons)


# ---------------------------------------------------------------------------
# Mixed real render: text -> Three, media -> Remotion, ONE mp4 via the
# pinned rendering.ffmpeg-finalizer.  Follows the hyperframes combined
# render's asset setup (ffmpeg lavfi source + real-assets.json registry).
# Skips ONLY for genuinely missing environment; a render failure is never
# turned into a skip.
# ---------------------------------------------------------------------------


def _mixed_timeline(tmp_path: Path) -> Path:
    """text [0, 0.5s) -> Three, silent media [0.5, 1.0s) -> Remotion."""
    path = tmp_path / "mixed-timeline.json"
    path.write_text(
        json.dumps(
            {
                "theme": "banodoco-default",
                "theme_overrides": {
                    "visual": {"canvas": dict(MIXED_CANVAS), "background": "#1a1a2e"}
                },
                "tracks": [{"id": "v1", "kind": "visual", "label": "Mixed"}],
                "clips": [
                    {
                        "id": "title",
                        "at": 0.0,
                        "track": "v1",
                        "clipType": "text",
                        "hold": 0.5,
                        "text": {"content": "MIXED", "fontSize": 64, "color": "#ffffff"},
                        "params": {"weight": 700},
                    },
                    {
                        "id": "media",
                        "at": 0.5,
                        "track": "v1",
                        "clipType": "media",
                        "asset": "src",
                        "from": 0,
                        "to": 0.5,
                        "speed": 1,
                        "volume": 0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _real_assets(tmp_path: Path, source: Path) -> Path:
    assets = tmp_path / "real-assets.json"
    assets.write_text(
        json.dumps(
            {
                "assets": {
                    "src": {
                        "file": source.name,
                        "type": "video/mp4",
                        "duration": 1.0,
                        "resolution": "320x180",
                        "fps": 24,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return assets


def _require_mixed_environment() -> None:
    from tests.packs.rendering.test_threejs_backend import _missing_environment

    missing = _missing_environment()
    if missing:
        pytest.skip(
            "mixed Three/Remotion render skipped: missing optional "
            "dependencies: " + ", ".join(missing)
        )


@pytest.mark.timeout(900)
def test_threejs_hybrid_mixed_real_render(tmp_path: Path) -> None:
    """The whole pipeline end-to-end: one mixed timeline where the hybrid
    planner routes text -> rendering.threejs and media -> rendering.remotion,
    finalized by the pinned rendering.ffmpeg-finalizer into ONE mp4.

    Locks: the exact planned windows (0,12)/(12,24) at 24fps, deterministic
    output bytes, the non-uniform content boundary (frame 0 = text, frame 12
    = media), and every provenance identity field (planner, finalizer,
    segment renderer ids + support decisions, both backend fragments, the
    retained legacy_v1 engine on the Three fragment, rendered audio).
    """
    _require_mixed_environment()
    source = _source_video(tmp_path, audio=True)
    assets = _real_assets(tmp_path, source)
    timeline = _mixed_timeline(tmp_path)
    backend_config = {"rendering.remotion": {}, "rendering.threejs": {}}

    output = tmp_path / "mixed.mp4"
    with _execution_env():
        published = render(
            timeline_path=timeline,
            assets_registry_path=assets,
            out_path=output,
            backend="rendering.threejs-hybrid",
            audio="rendered",
            backend_config=backend_config,
        )
        # Determinism: the same timeline renders byte-identical bytes.
        output2 = tmp_path / "mixed-2.mp4"
        published2 = render(
            timeline_path=timeline,
            assets_registry_path=assets,
            out_path=output2,
            backend="rendering.threejs-hybrid",
            audio="rendered",
            backend_config=backend_config,
        )

    first = Path(published)
    second = Path(published2)
    assert first.is_file() and first.stat().st_size > 0
    assert second.is_file() and second.stat().st_size > 0

    first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
    second_hash = hashlib.sha256(second.read_bytes()).hexdigest()
    assert first_hash == second_hash, "mixed render is not deterministic"

    sidecar = Path(f"{first}.provenance.json")
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["sha256"] == first_hash
    assert payload["engine"] == "rendering.threejs-hybrid"
    assert payload["audio_ownership"] == "rendered"
    routing = payload["routing"]
    assert routing["resolved_policy"]["planner"] == "rendering.threejs-hybrid"
    assert routing["resolved_policy"]["finalizer"] == "rendering.ffmpeg-finalizer"
    segments = payload["segments_v2"]
    assert [
        (s["renderer"]["id"], s["window"]["start_frame"], s["window"]["end_frame"])
        for s in segments
    ] == [
        ("rendering.threejs", 0, 12),
        ("rendering.remotion", 12, 24),
    ], segments
    for segment in segments:
        assert segment["renderer"]["support_decision"]["backend"] == segment["renderer"]["id"]
    fragments = payload["backend_fragments"]
    assert "rendering.threejs" in fragments
    assert "rendering.remotion" in fragments
    threejs_fragment = fragments["rendering.threejs"]
    assert threejs_fragment["renderer"] == "threejs"
    assert threejs_fragment["legacy_v1"]["engine"] == "threejs"
    assert fragments["rendering.remotion"]["renderer"] == "remotion"
    # The pinned finalizer contributes its own backend fragment: the service
    # merges it under the finalizer id with the ffmpeg finalizer shape.
    finalizer_fragment = fragments["rendering.ffmpeg-finalizer"]
    assert finalizer_fragment["finalizer_kind"] == "ffmpeg"
    assert isinstance(finalizer_fragment["finalizer_version"], str)
    assert finalizer_fragment["finalizer_version"]
    assert finalizer_fragment["segment_count"] == 2
    assert isinstance(finalizer_fragment["stream_copied_segments"], list)
    assert isinstance(finalizer_fragment["normalized_segments"], list)
    assert finalizer_fragment["audio_mode"] == "rendered"

    probe = _probe(first)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert "420p" in video["pix_fmt"], video
    assert video["width"] == 320 and video["height"] == 180
    assert video["time_base"] == "1/12288", video
    assert int(video["nb_read_frames"]) == 24, video
    numerator, denominator = (int(part) for part in video["avg_frame_rate"].split("/"))
    assert abs(numerator / denominator - 24.0) <= 1.0, video
    assert any(
        s["codec_type"] == "audio" and s["codec_name"] == "aac"
        for s in probe["streams"]
    )
    assert abs(float(probe["format"]["duration"]) - 1.0) < 0.1, probe

    # Non-uniform content: frame 0 shows the Three text, frame 12 the media.
    assert _frame_md5(first, 0) != _frame_md5(first, 12)
