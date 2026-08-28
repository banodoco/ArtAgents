"""Tests for FFmpeg text overlay support."""

from __future__ import annotations

from pathlib import Path

from astrid.core.rendering.contracts import RenderRequest, SCHEMA_VERSION
from astrid.packs.rendering.backends.ffmpeg.support import support as evaluate_support


def _text_timeline(*, extra_tracks: int = 0, text_params: dict | None = None) -> dict:
    """Create a text-only timeline."""
    tracks = [{"id": "v", "kind": "visual", "label": "Video"}]
    if extra_tracks > 0:
        for i in range(extra_tracks):
            tracks.append(
                {"id": f"v{i}", "kind": "visual", "label": f"Extra {i}", "priority": i + 1}
            )

    clips = [
        {
            "id": "t1",
            "clipType": "text",
            "track": "v",
            "at": 0,
            "hold": 4,
            "text": {
                "content": "Hello World",
                "fontSize": 48,
                "color": "#FFFFFF",
                "align": "center",
            },
        }
    ]
    return {"tracks": tracks, "clips": clips}


def _assets(tmp_path: Path, *, duration: float = 4.0) -> dict:
    """Create minimal assets registry."""
    # Create minimal video asset
    video_path = tmp_path / "test_video.mp4"
    video_path.write_bytes(b"fake video data")
    return {
        "assets": {
            "video1": {
                "type": "video",
                "path": "test_video.mp4",
                "duration": duration,
                "resolution": "1920x1080",
                "fps": 30,
            }
        }
    }


def _request(tmp_path: Path, timeline_data: dict, assets: dict) -> RenderRequest:
    """Create a RenderRequest for testing."""
    timeline_path = tmp_path / "timeline.json"
    assets_path = tmp_path / "assets.json"

    import json

    with open(timeline_path, "w") as f:
        json.dump(timeline_data, f)
    with open(assets_path, "w") as f:
        json.dump(assets, f)

    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name="output.mp4",
        backend_config={},

    )def _media_timeline(*, include_audio: bool = True) -> dict:
    """Create a media-only timeline."""
    tracks = [{"id": "v", "kind": "visual", "label": "Video"}]
    clips = [
        {
            "id": "video",
            "at": 0,
            "track": "v",
            "clipType": "media",
            "asset": "main",
            "from": 0,
            "to": 2,
            "speed": 1,
            "volume": 0,
        }
    ]
    if include_audio:
        tracks.append({"id": "a", "kind": "audio", "label": "Audio"})
        clips.append(
            {
                "id": "audio",
                "at": 0,
                "track": "a",
                "clipType": "media",
                "asset": "main",
                "from": 0,
                "to": 2,
                "speed": 1,
                "volume": 0.75,
            }
        )
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {
                "canvas": {"width": 1920, "height": 1080, "fps": 30}
            }
        },
        "tracks": tracks,
        "clips": clips,
    }




def test_support_accepts_text_clip() -> None:
    """Test that text clip is supported alongside visual media."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    # Create a timeline with both visual media and text
    timeline = _media_timeline()
    timeline["clips"].append(
        {
            "id": "title",
            "at": 0.5,
            "track": "v",
            "clipType": "text-card",
            "hold": 1,
        }
    )

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert report.supported, f"Text clip with visual media should be supported: {report.reasons}"


def test_support_rejects_bare_text_without_visual_media() -> None:
    """Test that bare text (no visual media) is rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    # Create a timeline with text but no media
    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "t1",
                "clipType": "text",
                "track": "v",
                "at": 0,
                "hold": 4,
                "text": {
                    "content": "Hello World",
                    "fontSize": 48,
                    "color": "#FFFFFF",
                    "align": "center",
                },
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("needs at least one visual media clip" in reason for reason in report.reasons)


def test_support_accepts_extra_text_tracks() -> None:
    """Test that extra visual tracks are accepted for text-only timelines."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = _text_timeline(extra_tracks=1)
    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert report.supported, f"Extra text tracks should be supported: {report.reasons}"


def test_support_rejects_media_with_fades() -> None:
    """Test that media clips with fades are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
                "from": 0,
                "to": 4,
                "params": {"fadeIn": 0.5, "fadeOut": 0.5},
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("media fades" in reason for reason in report.reasons)


def test_support_accepts_text_fades() -> None:
    """Test that text clips with fades are accepted."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = _text_timeline(text_params={"fadeIn": 0.5, "fadeOut": 0.5})
    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert report.supported, f"Text fades should be supported: {report.reasons}"


def test_support_rejects_media_with_unsupported_params() -> None:
    """Test that media clips with unsupported params are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
                "params": {"backgroundColor": "#000000"},
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("media params" in reason for reason in report.reasons)


def test_support_rejects_media_with_opacity_not_one() -> None:
    """Test that media clips with opacity != 1.0 are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
                "opacity": 0.5,
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("opacity" in reason for reason in report.reasons)


def test_support_rejects_media_with_overlapping_clips() -> None:
    """Test that overlapping media clips are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
            },
            {
                "id": "m2",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 2,
                "hold": 2,
            },
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("overlap" in reason for reason in report.reasons)


def test_support_rejects_media_with_transforms() -> None:
    """Test that media clips with transforms are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
                "x": 100,
                "y": 100,
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("transforms" in reason for reason in report.reasons)


def test_support_rejects_media_with_crop() -> None:
    """Test that media clips with crops are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
                "cropTop": 10,
                "cropBottom": 10,
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("crop" in reason for reason in report.reasons)


def test_support_rejects_media_with_effects() -> None:
    """Test that media clips with effects are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
                "effects": {"blur": 5},
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("effects" in reason for reason in report.reasons)


def test_support_rejects_media_with_transition() -> None:
    """Test that media clips with transitions are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
                "transition": "fade",
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("transition" in reason for reason in report.reasons)


def test_support_rejects_media_with_hold() -> None:
    """Test that media clips with hold are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "m1",
                "clipType": "media",
                "track": "v",
                "asset": "video1",
                "at": 0,
                "hold": 4,
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("hold" in reason for reason in report.reasons)


def test_support_rejects_audio_fades_on_text() -> None:
    """Test that text clips don't accept audio fades."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "t1",
                "clipType": "text",
                "track": "v",
                "at": 0,
                "hold": 4,
                "text": {
                    "content": "Hello World",
                    "fontSize": 48,
                    "color": "#FFFFFF",
                    "align": "center",
                },
                "params": {"fadeIn": 0.5},
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("fades" in reason for reason in report.reasons)


def test_support_rejects_unsupported_clip_kind() -> None:
    """Test that unsupported clip kinds are rejected."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "unknown1",
                "clipType": "unknown",
                "track": "v",
                "at": 0,
                "hold": 4,
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("unsupported clip kind" in reason for reason in report.reasons)


def test_support_text_params_validation() -> None:
    """Test that text params are validated correctly."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    # Test invalid color format
    timeline = _text_timeline(text_params={"color": "not-a-color"})
    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert not report.supported
    assert any("color" in reason.lower() and "format" in reason.lower() for reason in report.reasons)


def test_support_text_to_rgba_png_integration() -> None:
    """Test that text rasterization works in the support path."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "t1",
                "clipType": "text",
                "track": "v",
                "at": 0,
                "hold": 4,
                "text": {
                    "content": "Test Caption",
                    "fontSize": 48,
                    "color": "#FFFFFF",
                    "align": "center",
                    "textShadow": {"color": "#000000", "blur": 2, "offsetX": 2, "offsetY": 2},
                },
            }
        ],
    }

    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert report.supported, f"Text with shadow should be supported: {report.reasons}"


def test_support_text_fallback_to_bold_variant() -> None:
    """Test that text rasterization attempts bold variant."""
    tmp_path = Path("/tmp/test")
    tmp_path.mkdir(exist_ok=True)

    timeline = _text_timeline(text_params={"bold": True})
    report = evaluate_support(
        _request(tmp_path, timeline, _assets(tmp_path)),
        timeline,
        _assets(tmp_path),
    )
    assert report.supported, f"Bold text should be supported: {report.reasons}"