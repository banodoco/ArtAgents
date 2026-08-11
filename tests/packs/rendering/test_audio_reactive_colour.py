from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.timeline.validators.timeline import validate_timeline
from astrid.packs.rendering.executors.render import audio_reactive_colour
from astrid.packs.rendering.executors.render import run as render_run

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _timeline(*, events: list[dict] | None = None) -> dict:
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 640, "height": 360, "fps": 48}}
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
                "clipType": "audio-reactive-colour",
                "hold": 0.5,
                "params": {
                    "schemaVersion": 1,
                    "initialColor": "#102030",
                    "events": events
                    if events is not None
                    else [
                        {"id": "a", "frame": 3, "color": "#D47795"},
                        {"id": "b", "frame": 8, "color": "#26A7D0"},
                        {"id": "c", "frame": 17, "color": "#B59432"},
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
            },
        ],
    }


def _registry(audio_path: Path) -> dict:
    return {
        "assets": {
            "audio": {
                "file": str(audio_path),
                "type": "audio/wav",
                "duration": 0.5,
            }
        }
    }


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    audio_path = tmp_path / "tone.wav"
    audio_path.write_bytes(b"placeholder")
    timeline_path = tmp_path / "hype.timeline.json"
    assets_path = tmp_path / "hype.assets.json"
    timeline_path.write_text(json.dumps(_timeline()), encoding="utf-8")
    assets_path.write_text(json.dumps(_registry(audio_path)), encoding="utf-8")
    return timeline_path, assets_path, audio_path


def test_element_schema_and_fast_spec_accept_valid_timeline(tmp_path: Path) -> None:
    timeline_data = _timeline()
    validate_timeline(timeline_data)
    audio_path = tmp_path / "tone.wav"
    audio_path.write_bytes(b"placeholder")

    spec = audio_reactive_colour.match_and_validate(
        timeline_data, _registry(audio_path), tmp_path / "hype.assets.json"
    )

    assert spec is not None
    assert spec.total_frames == 24
    assert list(audio_reactive_colour.event_frames(spec)) == [3, 8, 17]
    assert len(spec.marker_sha256) == 64


@pytest.mark.parametrize(
    ("events", "message"),
    [
        (
            [
                {"frame": 8, "color": "#26A7D0"},
                {"frame": 3, "color": "#D47795"},
            ],
            "strictly increasing",
        ),
        (
            [
                {"frame": 3, "color": "#26A7D0"},
                {"frame": 3, "color": "#D47795"},
            ],
            "strictly increasing",
        ),
        ([{"frame": 24, "color": "#26A7D0"}], "below total frame count"),
        ([{"frame": 3, "color": "blue"}], "six-digit hex"),
    ],
)
def test_fast_spec_rejects_ambiguous_markers(
    tmp_path: Path, events: list[dict], message: str
) -> None:
    audio_path = tmp_path / "tone.wav"
    audio_path.write_bytes(b"placeholder")
    with pytest.raises(ValueError, match=message):
        audio_reactive_colour.match_and_validate(
            _timeline(events=events),
            _registry(audio_path),
            tmp_path / "hype.assets.json",
        )


@pytest.mark.parametrize("engine", ["remotion", "ffmpeg", "hybrid"])
def test_render_dispatches_compact_effect_to_ffmpeg_specialization(
    tmp_path: Path, engine: str
) -> None:
    timeline_path, assets_path, _audio_path = _write_inputs(tmp_path)
    out_path = tmp_path / engine / "hype.mp4"

    def fake_render(spec: audio_reactive_colour.AudioReactiveColourSpec, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        return output

    with patch.object(audio_reactive_colour, "render", side_effect=fake_render) as mocked:
        output = render_run.render(
            timeline_path,
            assets_path,
            out_path,
            engine=engine,
            keep_previous_renders=True,
        )

    assert output == out_path.resolve()
    mocked.assert_called_once()
    provenance = json.loads(
        Path(f"{out_path}.provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["engine"] == "ffmpeg"
    assert provenance["ffmpeg_specialization"] == "audio-reactive-colour/v1"
    assert provenance["audio_reactive_colour"]["event_count"] == 3
    assert provenance["audio_reactive_colour"]["frame_count"] == 24


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg and ffprobe are required")
def test_real_ffmpeg_render_has_exact_marker_frames_and_audio(tmp_path: Path) -> None:
    audio_path = tmp_path / "tone.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=0.5",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    spec = audio_reactive_colour.match_and_validate(
        _timeline(), _registry(audio_path), tmp_path / "hype.assets.json"
    )
    assert spec is not None
    out_path = audio_reactive_colour.render(spec, tmp_path / "render.mp4")

    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(out_path),
            "-vf",
            "crop=2:2:320:180,scale=1:1,format=rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    pixels = [raw[index : index + 3] for index in range(0, len(raw), 3)]
    changed = [
        index
        for index in range(1, len(pixels))
        if pixels[index] != pixels[index - 1]
    ]
    assert len(pixels) == 24
    assert changed == [3, 8, 17]

    streams = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames",
                "-of",
                "json",
                str(out_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    audio = next(stream for stream in streams if stream["codec_type"] == "audio")
    assert video["codec_name"] == "h264"
    assert video["width"] == 640
    assert video["height"] == 360
    assert video["r_frame_rate"] == "48/1"
    assert video["nb_frames"] == "24"
    assert audio["codec_name"] == "aac"
