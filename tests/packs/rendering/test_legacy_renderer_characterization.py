"""Characterization tests for the legacy monolith render path (T1.1).

These tests pin today's behavior of
``astrid/packs/rendering/executors/render/run.py`` so the later backend
extraction can be proven behavior-preserving. They never spawn a real render
(no ``npx remotion``, no ``ffmpeg``): engine routing, eligibility, provenance,
and duration math are exercised through the public helpers with heavy
dependencies mocked out.

Baseline recorded in ``.oracle/baseline.md`` (dirty-tree snapshot 6b2ff1a).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.packs.rendering.executors.render import audio_reactive_colour
from astrid.packs.rendering.executors.render import run as render_run


# ---------------------------------------------------------------------------
# fixture builders (plain dicts, no subprocesses)
# ---------------------------------------------------------------------------


def _media_only_timeline() -> dict:
    """A timeline the ffmpeg engine can fully service."""
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}
        },
        "tracks": [
            {"id": "v", "kind": "visual", "label": "Video"},
            {"id": "a", "kind": "audio", "label": "Audio"},
        ],
        "clips": [
            {
                "id": "clip_a",
                "at": 0,
                "track": "v",
                "clipType": "media",
                "asset": "main",
                "from": 0,
                "to": 2,
                "speed": 1,
                "volume": 0,
            },
            {
                "id": "clip_b",
                "at": 0,
                "track": "a",
                "clipType": "media",
                "asset": "main",
                "from": 0,
                "to": 2,
                "speed": 1,
                "volume": 1,
            },
        ],
    }


def _text_card_timeline() -> dict:
    """A media-only timeline plus a non-media clip (blocks the ffmpeg path)."""
    data = _media_only_timeline()
    data["clips"].append(
        {
            "id": "title",
            "at": 0.5,
            "track": "v",
            "clipType": "text-card",
            "hold": 1.0,
        }
    )
    return data


def _effect_clip_timeline() -> dict:
    """A media-only timeline whose visual clip carries an effect (complex)."""
    data = _media_only_timeline()
    data["clips"][0]["effects"] = [{"id": "zoom"}]
    return data


def _audio_reactive_timeline() -> dict:
    """The exact 2-clip shape the audio-reactive specialization accepts."""
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
        },
        "tracks": [
            {"id": "colour", "kind": "visual", "label": "Colour"},
            {"id": "audio", "kind": "audio", "label": "Audio"},
        ],
        "clips": [
            {
                "id": "colour_map",
                "at": 0,
                "track": "colour",
                "clipType": audio_reactive_colour.EFFECT_ID,
                "hold": 0.5,
                "params": {
                    "schemaVersion": 1,
                    "initialColor": "#102030",
                    "events": [
                        {"id": "a", "frame": 3, "color": "#D47795"},
                        {"id": "b", "frame": 8, "color": "#26A7D0"},
                    ],
                },
            },
            {
                "id": "source_audio",
                "at": 0,
                "track": "audio",
                "clipType": "media",
                "asset": "audio",
                "from": 0,
                "to": 0.5,
                "volume": 1,
            },
        ],
    }


def _write_timeline(tmp_path: Path, data: dict, name: str = "hype.timeline.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_assets(tmp_path: Path, name: str = "hype.assets.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"assets": {}}), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# engine dispatch selection (no real renders)
# ---------------------------------------------------------------------------


def test_engine_ffmpeg_dispatches_to_ffmpeg_media(tmp_path: Path) -> None:
    timeline_path = _write_timeline(tmp_path, _media_only_timeline())
    assets_path = _write_assets(tmp_path)
    out_path = tmp_path / "out" / "hype.mp4"
    sentinel = tmp_path / "sentinel.mp4"

    with (
        patch.object(render_run, "_render_audio_reactive_colour_if_supported", return_value=None),
        patch.object(render_run, "_render_ffmpeg_media", return_value=sentinel) as ffmpeg,
    ):
        result = render_run.render(timeline_path, assets_path, out_path, engine="ffmpeg")

    assert result == sentinel
    ffmpeg.assert_called_once_with(timeline_path, assets_path, out_path.resolve())


def test_engine_hybrid_dispatches_to_hybrid(tmp_path: Path) -> None:
    timeline_path = _write_timeline(tmp_path, _media_only_timeline())
    assets_path = _write_assets(tmp_path)
    out_path = tmp_path / "out" / "hype.mp4"
    sentinel = tmp_path / "sentinel.mp4"

    with (
        patch.object(render_run, "_render_audio_reactive_colour_if_supported", return_value=None),
        patch.object(render_run, "_render_hybrid", return_value=sentinel) as hybrid,
    ):
        result = render_run.render(
            timeline_path,
            assets_path,
            out_path,
            engine="hybrid",
            project_dir=tmp_path / "remotion",
            composition_id="CustomComposition",
            theme_path=tmp_path / "theme.json",
            min_free_gb=1.5,
        )

    assert result == sentinel
    hybrid.assert_called_once_with(
        timeline_path,
        assets_path,
        out_path.resolve(),
        project_dir=tmp_path / "remotion",
        composition_id="CustomComposition",
        theme_path=tmp_path / "theme.json",
        min_free_gb=1.5,
    )


def test_engine_remotion_media_only_auto_routes_to_ffmpeg(tmp_path: Path) -> None:
    """Nominal default engine still routes a media-only timeline to ffmpeg."""
    timeline_path = _write_timeline(tmp_path, _media_only_timeline())
    assets_path = _write_assets(tmp_path)
    out_path = tmp_path / "out" / "hype.mp4"
    sentinel = tmp_path / "sentinel.mp4"

    with (
        patch.object(render_run, "_render_audio_reactive_colour_if_supported", return_value=None),
        patch.object(render_run, "_render_ffmpeg_media", return_value=sentinel) as ffmpeg,
    ):
        result = render_run.render(timeline_path, assets_path, out_path, engine="remotion")

    assert result == sentinel
    ffmpeg.assert_called_once_with(timeline_path, assets_path, out_path.resolve())


def test_engine_remotion_complex_timeline_reaches_remotion_path(tmp_path: Path) -> None:
    """A non-media clip defeats auto-FFmpeg; the Remotion path is taken."""
    timeline_path = _write_timeline(tmp_path, _text_card_timeline())
    assets_path = _write_assets(tmp_path)
    out_path = tmp_path / "out" / "hype.mp4"

    with (
        patch.object(render_run, "_render_audio_reactive_colour_if_supported", return_value=None),
        patch.object(render_run, "_can_render_with_ffmpeg_media", return_value=False),
        patch.object(
            render_run.remotion_backend,
            "render",
            side_effect=AssertionError("reached remotion path"),
        ),
    ):
        with pytest.raises(AssertionError, match="reached remotion path"):
            render_run.render(timeline_path, assets_path, out_path, engine="remotion")


def test_unknown_engine_rejected(tmp_path: Path) -> None:
    timeline_path = _write_timeline(tmp_path, _media_only_timeline())
    assets_path = _write_assets(tmp_path)
    out_path = tmp_path / "out" / "hype.mp4"

    with patch.object(render_run, "_render_audio_reactive_colour_if_supported", return_value=None):
        with pytest.raises(ValueError, match="Unsupported render engine"):
            render_run.render(timeline_path, assets_path, out_path, engine="imovie")


# ---------------------------------------------------------------------------
# nominal-Remotion auto-FFmpeg eligibility
# ---------------------------------------------------------------------------


def test_can_render_with_ffmpeg_media_accepts_media_only_timeline(tmp_path: Path) -> None:
    timeline_path = _write_timeline(tmp_path, _media_only_timeline())
    assets_path = _write_assets(tmp_path)

    assert render_run._can_render_with_ffmpeg_media(timeline_path, assets_path) is True


def test_can_render_with_ffmpeg_media_rejects_text_card_timeline(tmp_path: Path) -> None:
    timeline_path = _write_timeline(tmp_path, _text_card_timeline())
    assets_path = _write_assets(tmp_path)

    assert render_run._can_render_with_ffmpeg_media(timeline_path, assets_path) is False


# ---------------------------------------------------------------------------
# audio-reactive early selection
# ---------------------------------------------------------------------------


def test_audio_reactive_specialization_contract_check(tmp_path: Path) -> None:
    """match_and_validate is the entry predicate: a valid 2-clip timeline yields a spec."""
    audio_path = tmp_path / "tone.wav"
    audio_path.write_bytes(b"placeholder")
    registry = {
        "assets": {
            "audio": {
                "file": str(audio_path),
                "type": "audio/wav",
                "duration": 0.5,
            }
        }
    }

    spec = audio_reactive_colour.match_and_validate(
        _audio_reactive_timeline(), registry, tmp_path / "hype.assets.json"
    )

    assert spec is not None
    assert spec.fps == 30
    assert spec.total_frames == 15  # hold 0.5s * 30fps
    assert len(spec.marker_sha256) == 64


def test_audio_reactive_selection_precedes_engine_dispatch(tmp_path: Path) -> None:
    """The specialization short-circuits even engine='hybrid'."""
    timeline_path = _write_timeline(tmp_path, _media_only_timeline())
    assets_path = _write_assets(tmp_path)
    out_path = tmp_path / "out" / "hype.mp4"
    sentinel = tmp_path / "audio_reactive.mp4"

    with (
        patch.object(
            render_run, "_render_audio_reactive_colour_if_supported", return_value=sentinel
        ) as specialized,
        patch.object(render_run, "_render_hybrid") as hybrid,
    ):
        result = render_run.render(timeline_path, assets_path, out_path, engine="hybrid")

    assert result == sentinel
    specialized.assert_called_once()
    hybrid.assert_not_called()


def test_audio_reactive_shape_gate_rejects_non_two_clip_timeline(tmp_path: Path) -> None:
    """3 clips -> None before any element/registry work."""
    data = _media_only_timeline()
    data["clips"].append({"id": "extra", "at": 0, "track": "v", "clipType": "text-card", "hold": 0.5})
    timeline_path = _write_timeline(tmp_path, data)
    assets_path = _write_assets(tmp_path)
    out_path = tmp_path / "out" / "hype.mp4"

    with patch.object(render_run, "_audio_reactive_ffmpeg_element") as element:
        result = render_run._render_audio_reactive_colour_if_supported(
            timeline_path,
            assets_path,
            out_path,
            project_dir=None,
            composition_id="TimelineComposition",
            theme_path=None,
        )

    assert result is None
    element.assert_not_called()


# ---------------------------------------------------------------------------
# v1 provenance keys
# ---------------------------------------------------------------------------


def test_render_provenance_v1_key_set(tmp_path: Path) -> None:
    out_path = tmp_path / "hype.mp4"
    timeline_path = tmp_path / "hype.timeline.json"
    assets_path = tmp_path / "hype.assets.json"
    timeline_path.write_text("{}", encoding="utf-8")
    assets_path.write_text("{}", encoding="utf-8")

    with patch.object(render_run, "_active_pack_order_for_provenance", return_value=[]):
        sidecar = render_run._write_render_provenance(
            out_path,
            engine="remotion",
            timeline_path=timeline_path,
            assets_path=assets_path,
            project_dir=tmp_path / "remotion",
            composition_id="TimelineComposition",
            theme_path=None,
            active_theme=None,
            registry_state={"hash": "abc123"},
            stage_summary={"root": None, "effects": []},
        )

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema_version",
        "engine",
        "output",
        "timeline",
        "assets_registry",
        "project_dir",
        "composition_id",
        "active_pack_order",
        "active_theme",
        "registry_hash",
        "registry_state",
        "resolved_effect_ids",
        "resolved_effects",
        "source_pack_ids",
        "element_roots",
        "staged_asset_ids",
        "staged_asset_root",
    }
    assert payload["schema_version"] == 1
    assert payload["engine"] == "remotion"
    assert payload["registry_hash"] == "abc123"
    assert payload["active_theme"] == {"id": "banodoco-default", "path": None}


def test_render_provenance_hybrid_adds_segment_keys(tmp_path: Path) -> None:
    out_path = tmp_path / "hype.mp4"
    timeline_path = tmp_path / "hype.timeline.json"
    assets_path = tmp_path / "hype.assets.json"
    timeline_path.write_text("{}", encoding="utf-8")
    assets_path.write_text("{}", encoding="utf-8")
    segments = [{"engine": "ffmpeg", "from": 0.0, "to": 1.0}]
    segment_provenance = [{"engine": "remotion", "output": "/tmp/seg.mp4"}]

    with patch.object(render_run, "_active_pack_order_for_provenance", return_value=[]):
        sidecar = render_run._write_render_provenance(
            out_path,
            engine="hybrid",
            timeline_path=timeline_path,
            assets_path=assets_path,
            project_dir=tmp_path / "remotion",
            composition_id="TimelineComposition",
            theme_path=None,
            active_theme=None,
            registry_state={"hash": "x"},
            stage_summary={"root": None, "effects": []},
            segments=segments,
            segment_provenance=segment_provenance,
        )

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["segments"] == segments
    assert payload["segment_provenance"] == segment_provenance


# ---------------------------------------------------------------------------
# transition units (pure math, no subprocess)
# ---------------------------------------------------------------------------


def test_timeline_duration_prefers_explicit_metadata() -> None:
    data = _media_only_timeline()
    data["metadata"] = {"duration_seconds": 12.5}
    assert render_run._timeline_duration_seconds(data) == 12.5


def test_timeline_duration_falls_back_to_expected_duration_seconds() -> None:
    data = _media_only_timeline()
    data["metadata"] = {"expected_duration_seconds": 7.25}
    assert render_run._timeline_duration_seconds(data) == 7.25


def test_timeline_duration_computed_from_clips_when_no_metadata() -> None:
    assert render_run._timeline_duration_seconds(_media_only_timeline()) == 2.0


def test_clip_duration_and_timeline_end_math() -> None:
    media_clip = {"at": 1.0, "from": 10.0, "to": 16.0, "speed": 2.0, "clipType": "media"}
    assert render_run._clip_duration_seconds(media_clip) == 3.0
    assert render_run._clip_timeline_end_seconds(media_clip) == 4.0

    hold_clip = {"at": 2.0, "clipType": "text-card", "hold": 1.5}
    assert render_run._clip_timeline_end_seconds(hold_clip) == 3.5

    to_clip = {"at": 0.0, "clipType": "text-card", "to": 5.0}
    assert render_run._clip_timeline_end_seconds(to_clip) == 5.0


def test_round_frame_time_modes() -> None:
    fps = 30
    assert render_run._round_frame_time(0.0167, fps, mode="floor") == 0.0
    assert render_run._round_frame_time(0.0167, fps, mode="ceil") == pytest.approx(1 / fps)
    assert render_run._round_frame_time(0.0167, fps, mode="round") == pytest.approx(1 / fps)
    assert render_run._round_frame_time(1 / fps, fps, mode="floor") == pytest.approx(1 / fps)
    assert render_run._round_frame_time(1 / fps, fps, mode="ceil") == pytest.approx(1 / fps)


def test_hybrid_segments_media_only_is_single_ffmpeg_segment() -> None:
    segments = render_run._hybrid_segments(_media_only_timeline())
    assert segments == [{"engine": "ffmpeg", "from": 0.0, "to": 2.0}]


def test_hybrid_segments_effect_clip_marks_remotion_window() -> None:
    segments = render_run._hybrid_segments(_effect_clip_timeline())
    assert segments == [{"engine": "remotion", "from": 0.0, "to": 2.0}]


# ---------------------------------------------------------------------------
# real transitions in _complex_clip_windows (default duration, precedence,
# handle padding, rounding)
# ---------------------------------------------------------------------------


def _two_media_clips_timeline(transition: dict | None) -> dict:
    """Two back-to-back media clips on one visual track (fps 30).

    clip_a spans [0, 2]; clip_b starts at 2.0 and spans [2, 4]. The timeline
    duration (no metadata) is 4.0. clip_a optionally carries *transition*.
    """
    clips = [
        {
            "id": "clip_a",
            "at": 0,
            "track": "v",
            "clipType": "media",
            "asset": "main",
            "from": 0,
            "to": 2,
            "speed": 1,
            "volume": 0,
        },
        {
            "id": "clip_b",
            "at": 2,
            "track": "v",
            "clipType": "media",
            "asset": "main",
            "from": 0,
            "to": 2,
            "speed": 1,
            "volume": 0,
        },
    ]
    if transition is not None:
        clips[0]["transition"] = transition
    return {
        "theme": "banodoco-default",
        "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": clips,
    }


def test_transition_default_duration_is_8_frames() -> None:
    """A transition dict without duration keys defaults to 8 frames / fps.

    For clip_a ending at 2.0 with the next clip at 2.0: window is
    (2.0 - 8/30 - 0.25, 2.0 + 8/30 + 0.25) floor/ceil-rounded to frames.
    """
    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"type": "crossfade"}), 30)
    assert windows == [
        (pytest.approx(44 / 30), pytest.approx(76 / 30)),
    ]


def test_transition_default_duration_scales_with_fps() -> None:
    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"type": "crossfade"}), 24)
    assert windows == [
        (pytest.approx(34 / 24), pytest.approx(62 / 24)),
    ]


def test_transition_duration_seconds_overrides_default() -> None:
    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"duration": 0.5}), 30)
    assert windows == [
        (pytest.approx(37 / 30), pytest.approx(83 / 30)),
    ]


def test_transition_duration_frames_divide_by_fps() -> None:
    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"durationFrames": 12}), 30)
    assert windows == [
        (pytest.approx(40 / 30), pytest.approx(80 / 30)),
    ]


def test_transition_duration_seconds_take_precedence_over_duration_frames() -> None:
    windows = render_run._complex_clip_windows(
        _two_media_clips_timeline({"duration": 0.5, "durationFrames": 12}), 30
    )
    assert windows == [
        (pytest.approx(37 / 30), pytest.approx(83 / 30)),
    ]


def test_transition_handle_padding_and_frame_rounding_without_transition() -> None:
    """An effect clip (no transition) is padded by handle_seconds=0.25 and the
    window is frame-rounded (floor start, ceil end)."""
    data = _two_media_clips_timeline(None)
    data["clips"][0]["effects"] = [{"id": "zoom"}]
    windows = render_run._complex_clip_windows(data, 30)
    # clip_a [0, 2] padded -> (max(0, 0-0.25), min(4, 2+0.25)) = (0, 2.25)
    # rounded -> frames 0 and ceil(2.25*30)=68.
    assert windows == [(0.0, pytest.approx(68 / 30))]


def test_transition_handle_padding_rounds_off_frame_boundaries() -> None:
    """A clip starting mid-frame pads to non-frame-aligned edges that are then
    rounded: at=0.5 hold=1.0 -> (0.5-0.25, 1.5+0.25) = (0.25, 1.75) -> frames 7/53."""
    data = {
        "theme": "banodoco-default",
        "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {"id": "card", "at": 0.5, "track": "v", "clipType": "text-card", "hold": 1.0},
            {"id": "media", "at": 0, "track": "v", "clipType": "media", "asset": "main", "from": 0, "to": 4, "speed": 1, "volume": 0},
        ],
    }
    windows = render_run._complex_clip_windows(data, 30)
    assert windows == [(pytest.approx(7 / 30), pytest.approx(53 / 30))]


def test_transition_takes_precedence_over_effect_window() -> None:
    """A media clip with BOTH effects and a transition uses the transition
    window (centered on the boundary), not the effect's padded clip window."""
    data = _two_media_clips_timeline({"duration": 0.5})
    data["clips"][0]["effects"] = [{"id": "zoom"}]
    windows = render_run._complex_clip_windows(data, 30)
    assert windows == [
        (pytest.approx(37 / 30), pytest.approx(83 / 30)),
    ]


def test_transition_ignored_for_non_media_clip() -> None:
    """'transition' is only honored on media clips: a text-card carrying a
    transition dict still gets the plain padded clip window."""
    data = {
        "theme": "banodoco-default",
        "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {"id": "card", "at": 0.5, "track": "v", "clipType": "text-card", "hold": 1.0, "transition": {"duration": 0.5}},
            {"id": "media", "at": 0, "track": "v", "clipType": "media", "asset": "main", "from": 0, "to": 4, "speed": 1, "volume": 0},
        ],
    }
    windows = render_run._complex_clip_windows(data, 30)
    assert windows == [(pytest.approx(7 / 30), pytest.approx(53 / 30))]


def test_transition_longer_than_clip_clamps_to_timeline_bounds() -> None:
    """A transition longer than the clip's lead-in clamps the window start to
    0 and the end to the timeline duration (with rounding)."""
    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"duration": 3.0}), 30)
    assert windows == [(0.0, pytest.approx(4.0))]


# ---------------------------------------------------------------------------
# standalone vs attached run ownership
# ---------------------------------------------------------------------------


def test_run_module_never_prepares_project_run() -> None:
    """run.py is standalone: it must not create a project run.json."""
    source = Path(render_run.__file__).read_text(encoding="utf-8")
    assert "prepare_project_run" not in source
    assert "run.json" not in source
    assert not hasattr(render_run, "prepare_project_run")


def test_main_parser_has_no_project_binding_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        render_run.main(["--help"])
    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    # "--project-dir" is the Remotion project directory, NOT a managed-binding
    # flag; "--project " (trailing space) would be the binding flag.
    assert "--project " not in help_text
    assert "--timeline-slug" not in help_text
    assert "--project-dir" in help_text
    assert "--engine" in help_text  # the only backend selection surface
