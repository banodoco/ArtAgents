from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from astrid.core.rendering import (
    Attachment,
    AudioOwnership,
    FrameWindow,
    RenderPlan,
    RenderProfile,
    RenderRequest,
    RenderResult,
    RendererError,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.contracts import (
    FinalizeRequest,
    FinalizerManifest,
    PlannerManifest,
    PROVENANCE_V1_COMPATIBILITY_KEYS,
    RenderSegment,
    RendererManifest,
    parse_wire_result,
)
from astrid.core.rendering.errors import RendererProtocolError
from astrid.core.rendering.provenance import (
    assemble_provenance_v2,
    hash_input_files,
    validate_backend_fragments,
    write_provenance_v2,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _profile(*, audio: bool = True) -> RenderProfile:
    return RenderProfile(
        width=1920,
        height=1080,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        container="mp4",
        video_codec="h264",
        video_profile="high",
        video_level="4.1",
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        duration_tolerance=1,
    )


def _window() -> FrameWindow:
    return FrameWindow(
        start_frame=0,
        end_frame=48,
        fps_rational=(24, 1),
        source_range=(10, 58),
        speed=1.0,
    )


def _support() -> SupportReport:
    return SupportReport(
        supported=True,
        reasons=[],
        features={"media": True, "audio_mode": "rendered"},
        alternatives=[],
        backend="acme.example",
        backend_version="1.0.0",
    )


def _segment() -> RenderSegment:
    return RenderSegment(
        window=_window(),
        backend="acme.example",
        backend_config={"acme.example": {"quality": "preview"}},
        support=_support(),
        input_hashes={"timeline": SHA_A},
    )


def _plan() -> RenderPlan:
    return RenderPlan(
        segments=[_segment()],
        finalizer="rendering.ffmpeg_finalizer",
        profile=_profile(),
        reasons={"0": "the request is supported"},
    )


def _video(*, attachments: dict[str, Attachment] | None = None) -> VideoArtifact:
    return VideoArtifact(
        path="outputs/video.mp4",
        profile=_profile(),
        sha256=SHA_A,
        duration_frames=48,
        audio=AudioOwnership.RENDERED,
        attachments=attachments or {},
    )


def test_dto_json_round_trip() -> None:
    request = RenderRequest(
        schema_version=1,
        timeline_path="/workspace/timeline.json",
        assets_registry_path="/workspace/assets.json",
        output_name="preview.mp4",
        window=_window(),
        audio=AudioOwnership.RENDERED,
        profile=_profile(),
        backend_config={"acme.example": {"quality": "preview"}},
        metadata={"project_id": "demo"},
    )
    alpha = Attachment(name="alpha.mov", path="outputs/alpha.mov", kind="alpha", sha256=SHA_B)
    project = Attachment(
        name="project.blend",
        path="outputs/project.blend",
        kind="project",
        sha256=SHA_C,
    )
    result = RenderResult(
        schema_version=1,
        video=_video(attachments={alpha.name: alpha}),
        attachments={project.name: project},
        backend_fragments={"acme.example": {"renderer": "example"}},
        audio_ownership=AudioOwnership.RENDERED,
        normalization=[],
        logs=["render completed"],
        metadata={"request_id": "render-001"},
    )
    error = RendererError(
        kind="unsupported",
        backend="acme.example",
        message="transitions are unsupported",
        recovery_command="select rendering.remotion",
        details={"features": ["transitions"]},
    )
    finalize = FinalizeRequest(
        schema_version=1,
        plan=_plan(),
        artifacts=[_video()],
        output_name="preview.mp4",
        backend_config={"rendering.ffmpeg_finalizer": {"faststart": True}},
        metadata={"request_id": "render-001"},
    )

    pairs = [
        (RenderRequest, request),
        (SupportReport, _support()),
        (RenderPlan, _plan()),
        (RenderResult, result),
        (RendererError, error),
        (FinalizeRequest, finalize),
    ]
    for dto_type, dto in pairs:
        payload = dto.to_dict()
        assert dto_type.from_dict(payload).to_dict() == payload


def test_optional_request_fields_default_and_selected_config_isolated() -> None:
    request = RenderRequest.from_dict(
        {
            "schema_version": 1,
            "timeline_path": "/workspace/timeline.json",
            "output_name": "video.mp4",
        }
    )
    assert request.assets_registry_path is None
    assert request.window is None
    assert request.audio is None
    assert request.profile is None
    assert request.backend_config == {}

    configured = RenderRequest(
        schema_version=1,
        timeline_path="/workspace/timeline.json",
        output_name="video.mp4",
        backend_config={
            "acme.example": {"quality": "high"},
            "rendering.remotion": {"composition": "TimelineComposition"},
        },
    )
    assert configured.for_backend("acme.example").backend_config == {
        "acme.example": {"quality": "high"}
    }


@pytest.mark.parametrize("version", [0, 2, "1", True, None])
def test_unknown_or_malformed_request_version_is_protocol_error(version: object) -> None:
    with pytest.raises(RendererProtocolError) as caught:
        RenderRequest.from_dict(
            {
                "schema_version": version,
                "timeline_path": "/workspace/timeline.json",
                "output_name": "video.mp4",
            }
        )
    assert caught.value.error.kind == "protocol"
    assert caught.value.error.backend == "astrid.core"


def test_unknown_request_top_level_field_is_protocol_error() -> None:
    with pytest.raises(RendererProtocolError) as caught:
        RenderRequest.from_dict(
            {
                "schema_version": 1,
                "timeline_path": "/workspace/timeline.json",
                "output_name": "video.mp4",
                "remotion_composition": "TimelineComposition",
            }
        )
    assert caught.value.error.kind == "protocol"


def test_direct_malformed_request_version_is_protocol_error() -> None:
    with pytest.raises(RendererProtocolError) as caught:
        RenderRequest(
            schema_version=True,
            timeline_path="/workspace/timeline.json",
            output_name="video.mp4",
        )
    assert caught.value.error.kind == "protocol"


def test_malformed_error_result_is_protocol_error() -> None:
    with pytest.raises(RendererProtocolError) as caught:
        parse_wire_result(
            {
                "kind": "unsupported",
                "backend": "acme.example",
                "message": "not supported",
            }
        )
    assert caught.value.error.kind == "protocol"


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 1), (0, 0), (2, 2), (3, 2), (True, 2)],
)
def test_invalid_frame_bounds_rejected(start: object, end: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        FrameWindow(start_frame=start, end_frame=end, fps_rational=(24, 1))


def test_partial_audio_profile_rejected() -> None:
    with pytest.raises(ValueError, match="provided together"):
        RenderProfile(
            width=1920,
            height=1080,
            fps_rational=(24, 1),
            time_base=(1, 12288),
            video_codec="h264",
            pixel_format="yuv420p",
            audio_codec="aac",
        )


def test_visual_only_profile_and_artifact_may_omit_optional_audio_fields() -> None:
    profile_payload = _profile(audio=False).to_dict()
    profile_payload.pop("audio_codec")
    profile_payload.pop("audio_sample_rate")
    profile_payload.pop("audio_channel_layout")
    profile = RenderProfile.from_dict(profile_payload)
    assert profile.has_audio is False

    artifact_payload = {
        "path": "outputs/visual.mp4",
        "profile": profile_payload,
        "sha256": SHA_A,
        "duration_frames": 48,
    }
    artifact = VideoArtifact.from_dict(artifact_payload)
    assert artifact.audio is None
    assert artifact.attachments == {}


def test_duplicate_attachment_names_rejected_across_result_surfaces() -> None:
    attachment = Attachment(
        name="alpha.mov",
        path="outputs/alpha.mov",
        kind="alpha",
        sha256=SHA_B,
    )
    with pytest.raises(ValueError, match="duplicate attachment names"):
        RenderResult(
            schema_version=1,
            video=_video(attachments={attachment.name: attachment}),
            attachments={attachment.name: attachment},
            backend_fragments={},
            audio_ownership=AudioOwnership.RENDERED,
            normalization=[],
            logs=[],
            metadata={},
        )


def test_attachment_mapping_key_must_match_name() -> None:
    attachment = Attachment(
        name="alpha.mov",
        path="outputs/alpha.mov",
        kind="alpha",
        sha256=SHA_B,
    )
    with pytest.raises(ValueError, match="must match attachment.name"):
        _video(attachments={"other.mov": attachment})


@pytest.mark.parametrize(
    "path",
    [
        "../escape.mp4",
        "outputs/../../escape.mp4",
        "outputs/./escape.mp4",
        "outputs//escape.mp4",
        "outputs/",
        "/tmp/escape.mp4",
        r"C:\\temp\\escape.mp4",
        r"\\\\server\\share\\escape.mp4",
    ],
)
def test_artifact_path_traversal_rejected(path: str) -> None:
    with pytest.raises(ValueError, match="workspace|contained|relative"):
        VideoArtifact(
            path=path,
            profile=_profile(),
            sha256=SHA_A,
            duration_frames=48,
            audio=AudioOwnership.RENDERED,
        )


def test_backend_fragment_cannot_overwrite_core_provenance_key() -> None:
    with pytest.raises(ValueError, match="core-owned keys: output"):
        validate_backend_fragments({"acme.example": {"output": "/tmp/stolen.mp4"}})

    with pytest.raises(ValueError, match="core-owned keys: resolved_backend"):
        RenderResult(
            schema_version=1,
            video=_video(),
            audio_ownership=AudioOwnership.RENDERED,
            backend_fragments={"acme.example": {"resolved_backend": "acme.example"}},
        )


def test_provenance_requires_always_emitted_v1_projection() -> None:
    with pytest.raises(ValueError, match="v1_compatibility is required"):
        assemble_provenance_v2(
            engine="remotion",
            output="/workspace/video.mp4",
            timeline="/workspace/timeline.json",
            assets_registry=None,
            requested_policy="remotion",
            resolved_backend="rendering.remotion",
            source_pack={"id": "rendering"},
            finalizer="rendering.ffmpeg_finalizer",
        )


def test_provenance_v2_preserves_v1_projection_and_namespace(tmp_path: Path) -> None:
    compatibility = {
        "project_dir": "/workspace/remotion",
        "composition_id": "TimelineComposition",
        "active_pack_order": [],
        "active_theme": None,
        "registry_hash": SHA_B,
        "registry_state": {},
        "resolved_effect_ids": [],
        "resolved_effects": [],
        "source_pack_ids": [],
        "element_roots": [],
        "staged_asset_ids": [],
        "staged_asset_root": None,
        "segment_provenance": [],
        "ffmpeg_specialization": None,
        "audio_reactive_colour": None,
    }
    assert set(compatibility) == set(PROVENANCE_V1_COMPATIBILITY_KEYS)
    kwargs = {
        "engine": "hybrid",
        "output": "/workspace/out/video.mp4",
        "timeline": "/workspace/timeline.json",
        "assets_registry": "/workspace/assets.json",
        "requested_policy": "hybrid",
        "resolved_backend": "acme.example",
        "source_pack": {"id": "acme"},
        "alias_chain": ["acme.alias", "acme.example"],
        "override": None,
        "trust_eligibility": {"eligible": True},
        "manifest_digest": SHA_C,
        "support_decision": _support(),
        "input_hashes": {"timeline": SHA_A},
        "segments": [_segment()],
        "artifact_profiles": {"outputs/video.mp4": _profile()},
        "audio_ownership": AudioOwnership.RENDERED,
        "normalization": [],
        "finalizer": "rendering.ffmpeg_finalizer",
        "attachments": {},
        "backend_fragments": {"acme.example": {"vendor": "Acme"}},
        "v1_compatibility": compatibility,
    }
    payload = assemble_provenance_v2(**kwargs)
    assert payload["schema_version"] == 2
    assert payload["engine"] == "hybrid"
    assert payload["resolved_backend"] == "acme.example"
    assert payload["segments"][0]["engine"] == "example"
    assert payload["segments"][0]["from"] == 0.0
    assert payload["segments"][0]["to"] == 2.0
    assert payload["composition_id"] == "TimelineComposition"
    assert payload["backend_fragments"] == {"acme.example": {"vendor": "Acme"}}

    sidecar = tmp_path / "video.mp4.provenance.json"
    assert write_provenance_v2(sidecar, **kwargs) == payload
    assert sidecar.read_text(encoding="utf-8").endswith("\n")


def test_shared_sha256_helper_is_used_for_input_hashes(tmp_path: Path) -> None:
    input_path = tmp_path / "timeline.json"
    input_path.write_text("abc", encoding="utf-8")
    hashes = hash_input_files({"timeline": input_path})
    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_contracts_are_frozen() -> None:
    window = _window()
    with pytest.raises(FrozenInstanceError):
        window.start_frame = 1  # type: ignore[misc]


def test_manifest_round_trip() -> None:
    common = {
        "schema_version": 1,
        "name": "Example",
        "version": "1.0.0",
        "protocol_version": 1,
        "command": ["python3", "backend.py"],
        "description": "Example implementation",
        "capabilities": {"features": {"media": True}},
        "required_permissions": ["project_files"],
        "required_binaries": [],
        "timeout_seconds": 60,
        "metadata": {"vendor": "Acme"},
    }
    cases = [
        (RendererManifest, {**common, "id": "acme.renderer", "operations": ["render", "support"]}),
        (PlannerManifest, {**common, "id": "acme.planner", "operations": ["plan"]}),
        (FinalizerManifest, {**common, "id": "acme.finalizer", "operations": ["finalize"]}),
    ]
    for manifest_type, payload in cases:
        assert manifest_type.from_dict(payload).to_dict() == payload


def test_manifest_dto_rejects_schema_invalid_capabilities_and_scalar_command() -> None:
    base = {
        "schema_version": 1,
        "id": "acme.renderer",
        "name": "Example",
        "version": "1.0.0",
        "protocol_version": 1,
        "operations": ["render"],
    }
    with pytest.raises(RendererProtocolError):
        RendererManifest.from_dict(
            {**base, "command": ["python3"], "capabilities": {"unknown": True}}
        )
    with pytest.raises(RendererProtocolError):
        RendererManifest.from_dict({**base, "command": "python3"})
