from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from astrid.core.rendering import (
    AudioOwnership,
    FrameWindow,
    RenderPlan,
    RenderProfile,
    RenderRequest,
    RenderResult,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.contracts import (
    FinalizeRequest,
    FinalizerManifest,
    PlannerManifest,
    RenderSegment,
    RendererManifest,
    parse_wire_result,
)


SCHEMA_DIR = (
    Path(__file__).resolve().parents[3]
    / "astrid"
    / "core"
    / "rendering"
    / "schemas"
    / "v1"
)
SCHEMA_NAMES = (
    "request.json",
    "result.json",
    "support.json",
    "plan.json",
    "finalize.json",
    "renderer-manifest.json",
    "planner-manifest.json",
    "finalizer-manifest.json",
)


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


PARSERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "request.json": RenderRequest.from_dict,
    "result.json": parse_wire_result,
    "support.json": SupportReport.from_dict,
    "plan.json": RenderPlan.from_dict,
    "finalize.json": FinalizeRequest.from_dict,
    "renderer-manifest.json": RendererManifest.from_dict,
    "planner-manifest.json": PlannerManifest.from_dict,
    "finalizer-manifest.json": FinalizerManifest.from_dict,
}


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_every_schema_and_example_is_valid_and_parses(schema_name: str) -> None:
    schema = _load_schema(schema_name)
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    examples = schema.get("examples")
    assert isinstance(examples, list) and examples, f"{schema_name} must carry examples"

    for example in examples:
        validator.validate(example)
        dto = PARSERS[schema_name](example)
        round_trip = dto.to_dict()
        validator.validate(round_trip)
        assert round_trip == example


def _profile() -> RenderProfile:
    return RenderProfile(
        width=1280,
        height=720,
        fps_rational=(30000, 1001),
        time_base=(1, 30000),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
        audio_codec=None,
        audio_sample_rate=None,
        audio_channel_layout=None,
        duration_tolerance=1,
    )


def test_python_dto_outputs_validate_against_source_schemas() -> None:
    profile = _profile()
    window = FrameWindow(
        start_frame=0,
        end_frame=60,
        fps_rational=(30000, 1001),
    )
    support = SupportReport(
        supported=True,
        reasons=[],
        features={"visual_only": True},
        alternatives=[],
        backend="acme.visual",
        backend_version=None,
    )
    segment = RenderSegment(
        window=window,
        backend="acme.visual",
        backend_config={"acme.visual": {}},
        support=support,
        input_hashes={"timeline": "a" * 64},
    )
    plan = RenderPlan(
        segments=[segment],
        finalizer="rendering.ffmpeg_finalizer",
        profile=profile,
        reasons={"0": "visual-only fixture"},
    )
    video = VideoArtifact(
        path="outputs/visual.mp4",
        profile=profile,
        sha256="b" * 64,
        duration_frames=60,
        audio=AudioOwnership.NONE,
        attachments={},
    )
    values = {
        "request.json": RenderRequest(
            schema_version=1,
            timeline_path="/workspace/timeline.json",
            output_name="visual.mp4",
            assets_registry_path=None,
            window=window,
            audio=AudioOwnership.NONE,
            profile=profile,
            backend_config={"acme.visual": {}},
            metadata={},
        ),
        "support.json": support,
        "plan.json": plan,
        "result.json": RenderResult(
            schema_version=1,
            video=video,
            audio_ownership=AudioOwnership.NONE,
        ),
        "finalize.json": FinalizeRequest(
            schema_version=1,
            plan=plan,
            artifacts=[video],
            output_name="visual.mp4",
            backend_config={"rendering.ffmpeg_finalizer": {}},
        ),
    }

    for schema_name, dto in values.items():
        jsonschema.Draft7Validator(_load_schema(schema_name)).validate(dto.to_dict())


def test_request_schema_rejects_backend_specific_top_level_field() -> None:
    request = {
        "schema_version": 1,
        "timeline_path": "/workspace/timeline.json",
        "output_name": "video.mp4",
        "remotion_composition": "TimelineComposition",
    }
    errors = list(jsonschema.Draft7Validator(_load_schema("request.json")).iter_errors(request))
    assert errors
    assert "Additional properties are not allowed" in errors[0].message


@pytest.mark.parametrize(
    "path",
    [
        "../escape.mp4",
        "outputs/./escape.mp4",
        "outputs//escape.mp4",
        "outputs/",
        "/tmp/escape.mp4",
        r"C:\\temp\\escape.mp4",
        r"dir\\escape.mp4",
    ],
)
def test_result_schema_rejects_uncontained_artifact_paths(path: str) -> None:
    result = {
        "schema_version": 1,
        "video": {
            "path": path,
            "profile": _profile().to_dict(),
            "sha256": "a" * 64,
            "duration_frames": 60,
            "audio": "none",
            "attachments": {},
        },
        "audio_ownership": "none",
    }
    errors = list(jsonschema.Draft7Validator(_load_schema("result.json")).iter_errors(result))
    assert errors


def test_result_schema_rejects_core_key_in_backend_fragment() -> None:
    result = RenderResult(
        schema_version=1,
        video=VideoArtifact(
            path="outputs/visual.mp4",
            profile=_profile(),
            sha256="a" * 64,
            duration_frames=60,
            audio=AudioOwnership.NONE,
        ),
        audio_ownership=AudioOwnership.NONE,
    ).to_dict()
    result["backend_fragments"] = {"acme.visual": {"timeline": "replacement"}}
    errors = list(jsonschema.Draft7Validator(_load_schema("result.json")).iter_errors(result))
    assert errors
