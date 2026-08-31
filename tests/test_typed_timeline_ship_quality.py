"""Ship-quality acceptance for typed rows -> timeline -> real video."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.packs.rendering.backends.ffmpeg.audio_reactive_colour import (
    match_and_validate,
    render,
)
from astrid.packs.typed_timeline.common import load_admitted_rows
from astrid.packs.typed_timeline.mapper import TypedDataTimelineMapper
from astrid.packs.typed_timeline.prompts import prompts_for_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNAWAY_RELEASE_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "runaway_release"
MANIFEST = RUNAWAY_RELEASE_FIXTURE_ROOT / "timing-manifest.json"
AUDIO_REACTIVE = RUNAWAY_RELEASE_FIXTURE_ROOT / "audio-reactive-v1.json"
RUNAWAY_COLOUR_GOLDEN_SHA256 = (
    "02c09dace0a838b56655beac58ad930b43089877d1d0803aca9dc99065f40481"
)
RUNAWAY_TEXT_GOLDEN_SHA256 = (
    "8fff606a64c04fc41ef3a13c6b6603cfce516a36765743e7c91f48d05e8c5145"
)
FULL_RENDER_ENV = "ASTRID_RUN_FULL_RENDER_ACCEPTANCE"


def _runaway_rows() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audio = json.loads(AUDIO_REACTIVE.read_text(encoding="utf-8"))
    transitions = manifest["transitions"]
    prompts = prompts_for_manifest(transitions)
    fps = manifest["clock"]["fps"]
    end_frame = audio["timebase"]["range_end_frame"]
    rows = []
    for ordinal, transition in enumerate(transitions):
        frame = transition["frame"]
        next_frame = transitions[ordinal + 1]["frame"] if ordinal + 1 < len(transitions) else end_frame
        metadata = {key: value for key, value in {
            "segment_id": transition.get("segment_id"),
            "segment_label": transition.get("segment_label"),
            "timing_mode": transition.get("timing_mode"),
            "colour_name": transition.get("colour_name"),
            "colour_hex": transition.get("colour_hex"),
            "colour_index": transition.get("colour_index"),
            "source_time_seconds": transition.get("source_time_seconds"),
            "grid_index": transition.get("grid_index"),
            "grid_time_seconds": transition.get("grid_time_seconds"),
            "frame": frame,
            "frame_time_seconds": transition.get("frame_time_seconds"),
            "frame_error_ms": transition.get("frame_error_ms"),
            "manifest_id": transition.get("id"),
            "command_time_seconds": transition.get("command_time_seconds"),
            "fps": fps,
            "range_end_frame": end_frame,
        }.items() if value is not None}
        rows.append({
            "ordinal": ordinal,
            "start_ms": int(round(frame * 1000 / fps)),
            "duration_ms": int(round((next_frame - frame) * 1000 / fps)),
            "prompt": prompts[ordinal],
            "metadata": metadata,
        })
    return rows


def _small_rows() -> list[dict]:
    colours = ("#FF0000", "#00FF00", "#0000FF", "#FFFF00")
    return [
        {
            "ordinal": ordinal,
            "start_ms": round(frame * 1000 / 24),
            "duration_ms": 500,
            "prompt": f"colour event {ordinal}",
            "metadata": {"frame": frame, "colour_hex": colour},
        }
        for ordinal, (frame, colour) in enumerate(
            zip((1, 12, 24, 36), colours, strict=True)
        )
    ]


def _small_mapping() -> dict:
    return {
        "schema_version": 1,
        "canvas": {"width": 320, "height": 180, "fps": 24, "total_frames": 48},
        "tracks": [
            {"id": "colour", "kind": "visual", "label": "Colour"},
            {"id": "audio", "kind": "audio", "label": "Audio"},
        ],
        "scope": "aggregated",
        "clip": {
            "id": "colour_map",
            "track": "colour",
            "clipType": "audio-reactive-colour",
            "initialColor": {"const": "#101010"},
            "events": {
                "frame": {"prefer": "metadata.frame"},
                "color": {"path": "metadata.colour_hex"},
                "id": {"path": "ordinal"},
            },
        },
        "audio_clip": {"id": "source_audio", "track": "audio", "asset": "audio"},
    }


def test_566_colour_and_text_mappings_are_exact_and_deterministic() -> None:
    rows = _runaway_rows()
    assert len(rows) == 566

    colour = TypedDataTimelineMapper(rows, "runaway_colour")
    colour_timeline = colour.to_timeline()
    events = colour_timeline["clips"][0]["params"]["events"]
    assert colour.total_frames == 8085
    assert len(events) == 566
    assert [event["frame"] for event in events] == sorted(
        {event["frame"] for event in events}
    )
    assert colour.hash() == RUNAWAY_COLOUR_GOLDEN_SHA256

    text = TypedDataTimelineMapper(list(reversed(rows)), "runaway_text")
    text_timeline = text.to_timeline()
    assert len(text_timeline["clips"]) == 566
    assert text.hash() == RUNAWAY_TEXT_GOLDEN_SHA256
    assert text.to_timeline() == text_timeline
    assert max(clip["at"] + clip["hold"] for clip in text_timeline["clips"]) == pytest.approx(
        8085 / 48
    )
    assert all(clip["params"]["content"].strip() for clip in text_timeline["clips"])


def test_mapper_rejects_duplicate_frames_invalid_colours_and_oversized_canvas() -> None:
    rows = _small_rows()
    duplicate = [dict(row) for row in rows]
    duplicate[1] = {**duplicate[1], "metadata": {**duplicate[1]["metadata"], "frame": 1}}
    with pytest.raises(ValueError, match="frames must be unique"):
        TypedDataTimelineMapper(duplicate, _small_mapping()).to_timeline()

    invalid_colour = [dict(row) for row in rows]
    invalid_colour[0] = {
        **invalid_colour[0],
        "metadata": {**invalid_colour[0]["metadata"], "colour_hex": "red"},
    }
    with pytest.raises(ValueError, match="#RRGGBB"):
        TypedDataTimelineMapper(invalid_colour, _small_mapping()).to_timeline()

    huge = _small_mapping()
    huge["canvas"] = {**huge["canvas"], "width": 100_000}
    with pytest.raises(ValueError, match="canvas dimensions"):
        TypedDataTimelineMapper(rows, huge).to_timeline()


def test_admitted_rows_fail_closed_on_path_escape_shape_and_size(tmp_path: Path) -> None:
    project_root = tmp_path / "demo"
    project_root.mkdir()
    (project_root / "project.json").write_text('{"name":"Demo"}\n', encoding="utf-8")
    outside = tmp_path.parent / "outside-typed-rows.json"
    outside.write_text(json.dumps(_small_rows()), encoding="utf-8")
    try:
        with pytest.raises(Exception):
            load_admitted_rows(
                source="runaway",
                json_path=outside,
                json_rows=None,
                project="demo",
                projects_root=tmp_path,
            )
    finally:
        outside.unlink(missing_ok=True)

    duplicate_ordinals = _small_rows()
    duplicate_ordinals[1]["ordinal"] = 0
    with pytest.raises(ValueError, match="ordinals must be unique"):
        load_admitted_rows(
            source="runaway",
            json_path=None,
            json_rows=duplicate_ordinals,
            project="demo",
            projects_root=tmp_path,
        )

    invalid_json = _small_rows()
    invalid_json[0]["metadata"]["not_json"] = float("nan")
    with pytest.raises(ValueError, match="finite JSON"):
        load_admitted_rows(
            source="runaway",
            json_path=None,
            json_rows=invalid_json,
            project="demo",
            projects_root=tmp_path,
        )


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg toolchain required")
def test_small_typed_timeline_real_render_has_exact_frame_count(tmp_path: Path) -> None:
    from astrid.packs.typed_timeline.common import ensure_tone_wav

    mapper = TypedDataTimelineMapper(_small_rows(), _small_mapping())
    timeline_path = tmp_path / "timeline.json"
    assets_path = tmp_path / "assets.json"
    output_path = tmp_path / "video.mp4"
    timeline_path.write_text(json.dumps(mapper.to_timeline()), encoding="utf-8")
    assets_path.write_text(json.dumps(mapper.to_assets()), encoding="utf-8")
    ensure_tone_wav(tmp_path / "tone.wav", mapper.total_duration_sec)
    spec = match_and_validate(mapper.to_timeline(), mapper.to_assets(), assets_path)
    assert spec is not None
    render(spec, output_path)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "csv=p=0",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert int(probe.stdout.strip()) == 48
    assert output_path.stat().st_size > 1_000


@pytest.mark.skipif(
    os.environ.get(FULL_RENDER_ENV) != "1",
    reason=f"set {FULL_RENDER_ENV}=1 for the release-candidate render gate",
)
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg toolchain required",
)
def test_566_timeline_real_render_decodes_with_exact_stream_contract(
    tmp_path: Path,
) -> None:
    """Render every Runaway transition and decode the complete RC artifact."""
    from astrid.packs.typed_timeline.common import ensure_tone_wav

    source_hashes = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (MANIFEST, AUDIO_REACTIVE)
    }
    mapper = TypedDataTimelineMapper(_runaway_rows(), "runaway_colour")
    timeline = mapper.to_timeline()
    assets = mapper.to_assets()
    assert mapper.hash() == RUNAWAY_COLOUR_GOLDEN_SHA256
    assert mapper.total_frames == 8085
    assert len(timeline["clips"][0]["params"]["events"]) == 566

    timeline_path = tmp_path / "timeline.json"
    assets_path = tmp_path / "assets.json"
    output_path = tmp_path / "runaway-566.mp4"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    assets_path.write_text(json.dumps(assets), encoding="utf-8")
    ensure_tone_wav(tmp_path / "tone.wav", mapper.total_duration_sec)
    spec = match_and_validate(timeline, assets, assets_path)
    assert spec is not None
    render(spec, output_path)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate,nb_read_frames",
            "-of",
            "json",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    streams = json.loads(probe.stdout)["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1280, 720)
    assert video["r_frame_rate"] == "48/1"
    assert int(video["nb_read_frames"]) == 8085
    assert any(stream["codec_type"] == "audio" for stream in streams)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output_path), "-f", "null", "-"],
        check=True,
        capture_output=True,
        timeout=360,
    )
    assert output_path.stat().st_size > 1_000
    assert source_hashes == {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (MANIFEST, AUDIO_REACTIVE)
    }


def test_map_executor_writes_portable_contained_manifest(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "project.json").write_text('{"name":"Demo"}\n', encoding="utf-8")
    mapping_path = project / "mapping.yaml"
    import yaml

    mapping_path.write_text(yaml.safe_dump(_small_mapping()), encoding="utf-8")
    out = tmp_path / "out"
    env = dict(os.environ)
    env.update(
        {
            "ASTRID_INTERNAL_INVOCATION": "1",
            "ASTRID_PROJECTS_ROOT": str(tmp_path),
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "astrid.packs.typed_timeline.executors.map.run",
            "--source",
            "runaway",
            "--mapping",
            str(mapping_path),
            "--project",
            "demo",
            "--json-rows",
            json.dumps(_small_rows(), separators=(",", ":")),
            "--out",
            str(out),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert {entry["path"] for entry in manifest["outputs"]} == {
        "timeline.json",
        "assets.json",
        "tone.wav",
    }
    assert str(tmp_path) not in json.dumps(manifest)
    assert all((out / entry["path"]).is_file() for entry in manifest["outputs"])
