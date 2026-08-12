from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

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
    FinalizerResolution,
    PlannerManifest,
    PlannerResolution,
    PROVENANCE_V1_COMPATIBILITY_KEYS,
    RenderSegment,
    RendererManifest,
    RendererResolution,
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
SHA_D = "d" * 64
SHA_E = "e" * 64


def _profile(*, audio: bool = True, fps: tuple[int, int] = (24, 1)) -> RenderProfile:
    return RenderProfile(
        width=1920,
        height=1080,
        fps_rational=fps,
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


def _window(
    start: int = 0,
    end: int = 48,
    *,
    fps: tuple[int, int] = (24, 1),
) -> FrameWindow:
    return FrameWindow(
        start_frame=start,
        end_frame=end,
        fps_rational=fps,
        source_range=(10 + start, 10 + end),
        speed=1.0,
    )


def _support(backend: str = "acme.example") -> SupportReport:
    return SupportReport(
        schema_version=1,
        supported=True,
        reasons=[],
        features={"media": True, "audio_mode": "rendered"},
        alternatives=[],
        backend=backend,
        backend_version="1.0.0",
    )


def _planner() -> PlannerResolution:
    return PlannerResolution(
        id="rendering.legacy_hybrid",
        source_pack={"id": "rendering"},
        manifest_digest=SHA_C,
        trust_eligibility={"eligible": True, "method": "source-tree"},
        alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
        override=None,
        support_decision=_support("rendering.legacy_hybrid"),
    )


def _renderer(backend: str = "acme.example", *, digest: str = SHA_B) -> RendererResolution:
    return RendererResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest=digest,
        alias_chain=[backend],
        override=None,
        support_decision=_support(backend),
        trust_eligibility={"eligible": True, "method": "source-tree"},
    )


def _finalizer() -> FinalizerResolution:
    return FinalizerResolution(
        id="rendering.ffmpeg-finalizer",
        source_pack={"id": "rendering"},
        manifest_digest=SHA_E,
        alias_chain=["ffmpeg-finalizer", "rendering.ffmpeg-finalizer"],
        override=None,
        trust_eligibility={"eligible": True, "method": "source-tree"},
        support_decision=_support("rendering.ffmpeg-finalizer"),
    )


def _segment(
    start: int = 0,
    end: int = 48,
    *,
    backend: str = "acme.example",
    fps: tuple[int, int] = (24, 1),
    digest: str = SHA_B,
    renderer: RendererResolution | None = None,
) -> RenderSegment:
    return RenderSegment(
        window=_window(start, end, fps=fps),
        renderer=renderer or _renderer(backend, digest=digest),
        input_hashes={"timeline": SHA_A},
    )


def _plan(
    *,
    segments: list[RenderSegment] | None = None,
    total_frames: int = 48,
    profile: RenderProfile | None = None,
    window: FrameWindow | None = None,
    planner: PlannerResolution | None = None,
    finalizer: FinalizerResolution | None = None,
) -> RenderPlan:
    selected = [_segment()] if segments is None else segments
    return RenderPlan(
        schema_version=1,
        request_digest=SHA_D,
        requested_policy="hybrid",
        planner=planner or _planner(),
        segments=selected,
        finalizer=finalizer or _finalizer(),
        profile=profile or _profile(),
        total_frames=total_frames,
        reasons={str(index): "the request is supported" for index in range(len(selected))},
        window=window,
    )


def _video(
    *,
    path: str = "outputs/video.mp4",
    duration_frames: int = 48,
    profile: RenderProfile | None = None,
    audio: AudioOwnership = AudioOwnership.RENDERED,
    attachments: dict[str, Attachment] | None = None,
) -> VideoArtifact:
    return VideoArtifact(
        path=path,
        profile=profile or _profile(),
        sha256=SHA_A,
        duration_frames=duration_frames,
        audio=audio,
        attachments=attachments or {},
    )


def _result(*, video: VideoArtifact | None = None) -> RenderResult:
    selected = video or _video()
    assert selected.audio is not None
    return RenderResult(
        schema_version=1,
        video=selected,
        backend_fragments={"acme.example": {"renderer": "example"}},
        audio_ownership=selected.audio,
        normalization=[],
        logs=["render completed"],
        metadata={"request_id": "render-001"},
    )


def _finalize(
    *,
    plan: RenderPlan | None = None,
    artifacts: list[VideoArtifact] | None = None,
) -> FinalizeRequest:
    selected_plan = plan or _plan()
    return FinalizeRequest(
        schema_version=1,
        plan=selected_plan,
        artifacts=[_video()] if artifacts is None else artifacts,
        output_name="preview.mp4",
        backend_config={"rendering.ffmpeg-finalizer": {"faststart": True}},
        metadata={"request_id": "render-001"},
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
    project = Attachment(
        name="project.blend",
        path="outputs/project.blend",
        kind="project",
        sha256=SHA_C,
    )
    result = _result(video=_video(attachments={project.name: project}))
    error = RendererError(
        schema_version=1,
        kind="unsupported",
        backend="acme.example",
        message="transitions are unsupported",
        recovery_command="select rendering.remotion",
        details={"features": ["transitions"]},
    )

    pairs = [
        (RenderRequest, request),
        (SupportReport, _support()),
        (RenderPlan, _plan()),
        (RenderResult, result),
        (RendererError, error),
        (FinalizeRequest, _finalize()),
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


def _versioned_payloads() -> dict[str, tuple[Callable[[dict[str, Any]], Any], dict[str, Any]]]:
    request = RenderRequest(
        schema_version=1,
        timeline_path="/workspace/timeline.json",
        output_name="video.mp4",
    ).to_dict()
    error = RendererError(
        schema_version=1,
        kind="unsupported",
        backend="acme.example",
        message="unsupported",
        recovery_command=None,
        details={},
    ).to_dict()
    return {
        "request": (RenderRequest.from_dict, request),
        "support": (SupportReport.from_dict, _support().to_dict()),
        "plan": (RenderPlan.from_dict, _plan().to_dict()),
        "finalize": (FinalizeRequest.from_dict, _finalize().to_dict()),
        "result-success": (parse_wire_result, _result().to_dict()),
        "result-error": (parse_wire_result, error),
    }


@pytest.mark.parametrize("case", ["missing", "boolean", "malformed", "unknown"])
@pytest.mark.parametrize("operation", list(_versioned_payloads()))
def test_every_wire_reader_rejects_missing_malformed_or_unknown_versions(
    operation: str,
    case: str,
) -> None:
    parser, base = _versioned_payloads()[operation]
    payload = deepcopy(base)
    if case == "missing":
        payload.pop("schema_version")
    else:
        payload["schema_version"] = {
            "boolean": True,
            "malformed": "1",
            "unknown": 2,
        }[case]
    with pytest.raises(RendererProtocolError) as caught:
        parser(payload)
    assert caught.value.error.kind == "protocol"
    assert caught.value.error.backend == "astrid.core"


def test_unknown_request_top_level_field_is_protocol_error() -> None:
    with pytest.raises(RendererProtocolError):
        RenderRequest.from_dict(
            {
                "schema_version": 1,
                "timeline_path": "/workspace/timeline.json",
                "output_name": "video.mp4",
                "remotion_composition": "TimelineComposition",
            }
        )


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


def test_visual_only_profile_may_omit_nullable_audio_fields() -> None:
    profile_payload = _profile(audio=False).to_dict()
    profile_payload.pop("audio_codec")
    profile_payload.pop("audio_sample_rate")
    profile_payload.pop("audio_channel_layout")
    profile = RenderProfile.from_dict(profile_payload)
    artifact = VideoArtifact.from_dict(
        {
            "path": "outputs/visual.mp4",
            "profile": profile_payload,
            "sha256": SHA_A,
            "duration_frames": 48,
        }
    )
    assert profile.has_audio is False
    assert artifact.audio is None
    assert artifact.attachments == {}


def test_artifact_audio_ownership_matches_profile_presence() -> None:
    with pytest.raises(ValueError, match="audio profile"):
        _video(profile=_profile(audio=False), audio=AudioOwnership.RENDERED)
    with pytest.raises(ValueError, match="must declare audio='rendered'"):
        _video(profile=_profile(), audio=AudioOwnership.PASSTHROUGH)

    passthrough = _video(profile=_profile(audio=False), audio=AudioOwnership.PASSTHROUGH)
    assert _result(video=passthrough).audio_ownership is AudioOwnership.PASSTHROUGH


def test_explicit_request_audio_ownership_matches_explicit_profile() -> None:
    with pytest.raises(ValueError, match="audio profile"):
        RenderRequest(
            schema_version=1,
            timeline_path="timeline.json",
            output_name="video.mp4",
            audio=AudioOwnership.RENDERED,
            profile=_profile(audio=False),
        )
    with pytest.raises(ValueError, match="must declare audio='rendered'"):
        RenderRequest(
            schema_version=1,
            timeline_path="timeline.json",
            output_name="video.mp4",
            audio=AudioOwnership.NONE,
            profile=_profile(),
        )

    unresolved = RenderRequest(
        schema_version=1,
        timeline_path="timeline.json",
        output_name="video.mp4",
        audio=None,
        profile=_profile(),
    )
    assert unresolved.audio is None


def test_result_requires_video_audio_to_match_top_level_ownership() -> None:
    video = _video()
    with pytest.raises(ValueError, match="must be present and match"):
        RenderResult(
            schema_version=1,
            video=video,
            audio_ownership=AudioOwnership.NONE,
        )


def _attachment(name: str, *, sha256: str = SHA_B) -> Attachment:
    return Attachment(name=name, path=f"outputs/{name}", kind="project", sha256=sha256)


def test_video_is_the_only_authoritative_attachment_surface() -> None:
    attachment = _attachment("project.blend")
    result = _result(video=_video(attachments={attachment.name: attachment}))
    assert result.attachments == {attachment.name: attachment}
    assert "attachments" not in result.to_dict()
    with pytest.raises(RendererProtocolError):
        RenderResult.from_dict({**result.to_dict(), "attachments": {}})


def test_finalize_round_trip_preserves_global_segment_attachments() -> None:
    first = _attachment("first.blend", sha256=SHA_B)
    second = _attachment("second.blend", sha256=SHA_C)
    plan = _plan(segments=[_segment(0, 24), _segment(24, 48)])
    request = _finalize(
        plan=plan,
        artifacts=[
            _video(path="segments/0.mp4", duration_frames=24, attachments={first.name: first}),
            _video(path="segments/1.mp4", duration_frames=24, attachments={second.name: second}),
        ],
    )
    round_trip = FinalizeRequest.from_dict(request.to_dict())
    assert round_trip.expected_attachments == {first.name: first, second.name: second}

    final_video = _video(attachments={first.name: first, second.name: second})
    assert request.validate_final_result(_result(video=final_video)).video == final_video


def test_finalize_rejects_attachment_name_collisions_across_segments() -> None:
    attachment = _attachment("same.blend")
    plan = _plan(segments=[_segment(0, 24), _segment(24, 48)])
    with pytest.raises(ValueError, match="duplicate attachment names across segment"):
        _finalize(
            plan=plan,
            artifacts=[
                _video(path="segments/0.mp4", duration_frames=24, attachments={attachment.name: attachment}),
                _video(path="segments/1.mp4", duration_frames=24, attachments={attachment.name: attachment}),
            ],
        )


def test_finalize_rejects_dropped_or_changed_attachments() -> None:
    attachment = _attachment("project.blend")
    request = _finalize(artifacts=[_video(attachments={attachment.name: attachment})])
    with pytest.raises(ValueError, match="dropped attachments"):
        request.validate_final_result(_result())

    changed = _attachment("project.blend", sha256=SHA_C)
    with pytest.raises(ValueError, match="changed attachments"):
        request.validate_final_result(_result(video=_video(attachments={changed.name: changed})))


def test_attachment_mapping_key_must_match_name() -> None:
    with pytest.raises(ValueError, match="must match attachment.name"):
        _video(attachments={"other.blend": _attachment("project.blend")})


@pytest.mark.parametrize(
    "path",
    [
        "../escape.mp4",
        "outputs/../../escape.mp4",
        "outputs/./escape.mp4",
        "outputs//escape.mp4",
        "outputs/",
        "/tmp/escape.mp4",
        "C:escape.mp4",
        r"C:\\temp\\escape.mp4",
        r"\\\\server\\share\\escape.mp4",
    ],
)
def test_artifact_path_traversal_and_windows_drives_rejected(path: str) -> None:
    with pytest.raises(ValueError, match="workspace|contained|relative"):
        _video(path=path)


def test_backend_fragment_cannot_overwrite_current_or_retired_core_keys() -> None:
    for key in ("output", "planner", "resolved_backend", "request_digest"):
        with pytest.raises(ValueError, match=f"core-owned keys: {key}"):
            validate_backend_fragments({"acme.example": {key: "stolen"}})


def _compatibility() -> dict[str, Any]:
    return {
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
        "segment_provenance": [{"engine": "spoofed", "from": -1, "to": -1}],
        "ffmpeg_specialization": None,
        "audio_reactive_colour": None,
    }


def test_provenance_requires_always_emitted_v1_projection() -> None:
    with pytest.raises(ValueError, match="v1_compatibility is required"):
        assemble_provenance_v2(
            engine="remotion",
            output="/workspace/video.mp4",
            timeline="/workspace/timeline.json",
            assets_registry=None,
            plan=_plan(),
        )


def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: Path) -> None:
    compatibility = _compatibility()
    assert set(compatibility) == set(PROVENANCE_V1_COMPATIBILITY_KEYS)
    plan = _plan(
        segments=[
            _segment(0, 24, backend="acme.first", digest=SHA_B),
            _segment(24, 48, backend="other.second", digest=SHA_C),
        ]
    )
    kwargs = {
        "engine": "hybrid",
        "output": "/workspace/out/video.mp4",
        "timeline": "/workspace/timeline.json",
        "assets_registry": "/workspace/assets.json",
        "plan": plan,
        "artifact_profiles": {
            "outputs/video.mp4": {
                "profile": _profile(),
                "sha256": SHA_B,
                "attachments": {},
            },
            "outputs/segment2.mp4": {
                "profile": _profile(),
                "sha256": SHA_C,
                "attachments": {},
            },
        },
        "audio_ownership": AudioOwnership.RENDERED,
        "normalization": [],
        "attachments": {},
        "backend_fragments": {"acme.first": {"vendor": "Acme"}},
        "v1_compatibility": compatibility,
    }
    payload = assemble_provenance_v2(**kwargs)
    assert payload["schema_version"] == 2
    assert payload["request_digest"] == SHA_D
    assert payload["requested_policy"] == "hybrid"
    assert payload["planner"] == _planner().to_dict()
    assert [segment["renderer"]["id"] for segment in payload["segments_v2"]] == [
        "acme.first",
        "other.second",
    ]
    assert payload["segments_v2"] == [segment.to_dict() for segment in plan.segments]
    assert [set(segment) for segment in payload["segments_v2"]] == [
        {"window", "renderer", "input_hashes"},
        {"window", "renderer", "input_hashes"},
    ]
    # V1-compatible projections are preserved unchanged.
    assert payload["segments"] == [
        {"engine": "first", "from": 0.0, "to": 1.0},
        {"engine": "second", "from": 1.0, "to": 2.0},
    ]
    # segment_provenance passes through from the v1 compatibility projection
    # verbatim — the host never rewrites it.
    assert payload["segment_provenance"] == compatibility["segment_provenance"]
    assert payload["finalizer"] == _finalizer().to_dict()
    assert payload["composition_id"] == "TimelineComposition"

    sidecar = tmp_path / "video.mp4.provenance.json"
    assert write_provenance_v2(sidecar, **kwargs) == payload
    assert sidecar.read_text(encoding="utf-8").endswith("\n")


def test_provenance_rejects_spoofed_segment_projection_in_plan_mapping() -> None:
    plan = _plan().to_dict()
    plan["segments"][0]["engine"] = "spoofed"
    with pytest.raises(RendererProtocolError):
        assemble_provenance_v2(
            engine="hybrid",
            output="out/video.mp4",
            timeline="timeline.json",
            assets_registry=None,
            plan=plan,
            v1_compatibility=_compatibility(),
        )


def test_compute_request_digest_is_canonical_and_stable() -> None:
    from astrid.core.rendering.contracts import compute_request_digest

    a = {"backend_config": {"acme.visual": {"quality": "preview"}}, "schema_version": 1}
    b = {"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}}}
    assert compute_request_digest(a) == compute_request_digest(b)
    digest = compute_request_digest(a)
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert compute_request_digest({**a, "metadata": {"x": "y"}}) != digest
    assert compute_request_digest({"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}, "other.key": {}}}) != digest


def test_shared_sha256_helper_is_used_for_input_hashes(tmp_path: Path) -> None:
    input_path = tmp_path / "timeline.json"
    input_path.write_text("abc", encoding="utf-8")
    hashes = hash_input_files({"timeline": input_path})
    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
    """Non-default alias/override/trust/support evidence must survive the
    plan wire round-trip and the final provenance sidecar."""
    planner = replace(
        _planner(),
        alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
        override={"from": "acme.hybrid-planner", "to": "rendering.legacy_hybrid"},
        support_decision=_support("rendering.legacy_hybrid"),
    )
    renderer = replace(
        _renderer("acme.visual"),
        alias_chain=["visual", "acme.visual"],
        override={"from": "acme.visual-2", "to": "acme.visual"},
        trust_eligibility={"eligible": True, "method": "source-tree"},
    )
    finalizer = replace(
        _finalizer(),
        alias_chain=["finalizer", "rendering.ffmpeg-finalizer"],
        override={"from": "acme.finalizer-2", "to": "rendering.ffmpeg-finalizer"},
        trust_eligibility={"eligible": True, "method": "source-tree"},
        support_decision=_support("rendering.ffmpeg-finalizer"),
    )
    plan = _plan(
        planner=planner,
        segments=[
            _segment(0, 24, renderer=renderer),
            _segment(24, 48),
        ],
        finalizer=finalizer,
    )

    # Wire round-trip
    reparsed = RenderPlan.from_dict(plan.to_dict())
    assert reparsed.planner.alias_chain == planner.alias_chain
    assert reparsed.planner.override == planner.override
    assert reparsed.planner.support_decision is not None
    assert reparsed.segments[0].renderer.trust_eligibility == renderer.trust_eligibility
    assert reparsed.finalizer.alias_chain == finalizer.alias_chain
    assert reparsed.finalizer.trust_eligibility == finalizer.trust_eligibility
    assert reparsed.finalizer.support_decision is not None

    # Provenance sidecar carries the same evidence
    payload = assemble_provenance_v2(
        engine="hybrid",
        output="/workspace/out/video.mp4",
        timeline="/workspace/timeline.json",
        assets_registry=None,
        plan=plan,
        artifact_profiles={
            "outputs/visual.mp4": {
                "profile": _profile(),
                "sha256": SHA_B,
                "attachments": {},
            },
            "outputs/segment2.mp4": {
                "profile": _profile(),
                "sha256": SHA_C,
                "attachments": {},
            }
        },
        audio_ownership="rendered",
        normalization=[],
        attachments={},
        backend_fragments={},
        v1_compatibility=_compatibility(),
    )
    assert payload["planner"]["alias_chain"] == planner.alias_chain
    assert payload["planner"]["override"] == planner.override
    assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
    assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
    assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
    assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility


def test_resolution_records_require_all_seven_evidence_keys() -> None:
    """Every capability resolution requires the complete evidence set;
    a missing key is a structural protocol failure."""
def test_resolution_records_require_all_seven_evidence_keys() -> None:
    """Every capability resolution requires the complete evidence set;
    a missing key is a structural protocol failure."""
    cases = (
        (_planner(), PlannerResolution.from_dict),
        (_finalizer(), FinalizerResolution.from_dict),
        (_renderer(), RendererResolution.from_dict),
    )
    for obj, parser in cases:
        for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
            broken = obj.to_dict()
            del broken[missing]
            with pytest.raises(ValueError, match="missing required fields"):
                parser(broken)


def test_provenance_emits_hashed_artifact_lineage() -> None:
    """Provenance records per-artifact sha256 and attachment hashes, not
    just profiles — so replay can verify rendered outputs byte-for-byte."""
    artifact = VideoArtifact(
        path="outputs/visual.mp4",
        profile=_profile(),
        sha256=SHA_B,
        duration_frames=48,
        audio=AudioOwnership.RENDERED,
        attachments={
            "alpha": Attachment(
                name="alpha",
                path="outputs/alpha.mp4",
                kind="alpha",
                sha256=SHA_C,
            )
        },
    )
    payload = assemble_provenance_v2(
        engine="hybrid",
        output="/workspace/out/video.mp4",
        timeline="/workspace/timeline.json",
        assets_registry=None,
        plan=_plan(),
        artifact_profiles={"outputs/visual.mp4": artifact},
        audio_ownership="rendered",
        normalization=[],
        attachments={},
        backend_fragments={},
        v1_compatibility=_compatibility(),
    )
    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
    assert lineage["sha256"] == SHA_B
    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
    assert lineage["attachments"]["alpha"]["kind"] == "alpha"


def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
    """support_decision.backend must equal the resolution id for planner and
    finalizer, exactly as it does for renderer."""
    cases = (
        (_planner, "planner"),
        (_finalizer, "finalizer"),
        (_renderer, "renderer"),
    )
    for factory, label in cases:
        payload = factory().to_dict()
        payload["support_decision"] = _support("other.backend").to_dict()
        with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
            type(factory()).from_dict(payload)


def test_resolutions_reject_incoherent_override_records() -> None:
    """Override records must be {from, to} with to == resolution id."""
    cases = (
        (_planner, "planner"),
        (_finalizer, "finalizer"),
        (_renderer, "renderer"),
    )
    for factory, label in cases:
        payload = factory().to_dict()
        payload["override"] = {"from": "other.origin", "to": "not.the.id"}
        with pytest.raises(ValueError, match=f"{label} override 'to'"):
            type(factory()).from_dict(payload)
        payload["override"] = {"only": "one"}
        with pytest.raises(ValueError, match=f"{label} override"):
            type(factory()).from_dict(payload)


def test_provenance_rejects_spoofed_artifact_lineage() -> None:
    """Artifact lineage must carry a real sha256; profile-only entries and
    null hashes are rejected rather than stringified."""
    base = dict(
        engine="hybrid",
        output="/workspace/out/video.mp4",
        timeline="/workspace/timeline.json",
        assets_registry=None,
        audio_ownership="rendered",
        normalization=[],
        attachments={},
        backend_fragments={},
        v1_compatibility=_compatibility(),
    )
    with pytest.raises(TypeError, match="hashed lineage"):
        assemble_provenance_v2(
            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
        )
    with pytest.raises(ValueError, match="sha256"):
        assemble_provenance_v2(
            **base,
            plan=_plan(),
            artifact_profiles={
                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
            },
        )
    with pytest.raises(ValueError, match="sha256"):
        assemble_provenance_v2(
            **base,
            plan=_plan(),
            artifact_profiles={
                "out/v.mp4": {
                    "profile": _profile(),
                    "sha256": "not-a-hash",
                    "attachments": {},
                }
            },
        )
    with pytest.raises(ValueError, match="unknown fields"):
        assemble_provenance_v2(
            **base,
            plan=_plan(),
            artifact_profiles={
                "out/v.mp4": {
                    "profile": _profile(),
                    "sha256": SHA_B,
                    "attachments": {},
                    "spoof": 1,
                }
            },
        )
    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
        assemble_provenance_v2(
            **base,
            plan=_plan(
                segments=[_segment(0, 24), _segment(24, 48)]
            ),
            artifact_profiles={
                "out/v.mp4": {
                    "profile": _profile(),
                    "sha256": SHA_B,
                    "attachments": {},
                }
            },
        )
    with pytest.raises(ValueError, match="attachment path"):
        assemble_provenance_v2(
            **base,
            plan=_plan(),
            artifact_profiles={
                "out/v.mp4": {
                    "profile": _profile(),
                    "sha256": SHA_B,
                    "attachments": {
                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
                    },
                },
            },
        )
    with pytest.raises(ValueError, match="attachment kind"):
        assemble_provenance_v2(
            **base,
            plan=_plan(),
            artifact_profiles={
                "out/v.mp4": {
                    "profile": _profile(),
                    "sha256": SHA_B,
                    "attachments": {
                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
                    },
                },
            },
        )


    with pytest.raises(ValueError, match="must equal Attachment.name"):
        assemble_provenance_v2(
            **base,
            plan=_plan(),
            artifact_profiles={
                "out/v.mp4": {
                    "profile": _profile(),
                    "sha256": SHA_B,
                    "attachments": {
                        "different_key": Attachment(
                            name="alpha",
                            path="outputs/alpha.mp4",
                            kind="alpha",
                            sha256=SHA_C,
                        )
                    },
                }
            },
        )
    with pytest.raises(ValueError, match="duplicate attachment name"):
        assemble_provenance_v2(
            **base,
            plan=_plan(
                segments=[_segment(0, 24), _segment(24, 48)]
            ),
            artifact_profiles={
                "out/v1.mp4": {
                    "profile": _profile(),
                    "sha256": SHA_B,
                    "attachments": {
                        "alpha": {"path": "outputs/a.mp4", "kind": "alpha", "sha256": SHA_C}
                    },
                },
                "out/v2.mp4": {
                    "profile": _profile(),
                    "sha256": SHA_D,
                    "attachments": {
                        "alpha": {"path": "outputs/a2.mp4", "kind": "alpha", "sha256": SHA_C}
                    },
                },
            },
        )
    with pytest.raises(ValueError, match="workspace path"):
        assemble_provenance_v2(
            **base,
            plan=_plan(),
            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
        )
    with pytest.raises(ValueError, match="duplicate path"):
        assemble_provenance_v2(
            **base,
            plan=_plan(
                segments=[_segment(0, 24), _segment(24, 48)]
            ),
            artifact_profiles=[
                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
            ],
        )


def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
    plan = _plan(
        segments=[_segment(12, 24), _segment(24, 36)],
        total_frames=48,
        window=_window(12, 36),
    )
    assert plan.total_frames == 48
    assert plan.window == _window(12, 36)


@pytest.mark.parametrize(
    ("segments", "total_frames", "match"),
    [
        ([_segment(1, 48)], 48, "gap"),
        ([_segment(0, 47)], 48, "trailing gap"),
        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
        ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
        ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
    ],
)
def test_plan_rejects_gaps_overlaps_and_out_of_order_segments(
    segments: list[RenderSegment],
    total_frames: int,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        _plan(segments=segments, total_frames=total_frames)


def test_plan_rejects_noncanonical_segment_or_window_fps() -> None:
    with pytest.raises(ValueError, match="segment.*FPS"):
        _plan(segments=[_segment(fps=(48, 2))])
    with pytest.raises(ValueError, match="window FPS"):
        _plan(window=_window(0, 48, fps=(48, 2)))


def test_zero_frame_plan_semantics_and_no_finalization() -> None:
    empty = _plan(segments=[], total_frames=0, profile=_profile(audio=False))
    assert empty.segments == []
    assert empty.reasons == {}
    with pytest.raises(ValueError, match="zero-frame plan"):
        _plan(segments=[_segment()], total_frames=0)
    with pytest.raises(ValueError, match="positive-frame plan"):
        _plan(segments=[], total_frames=48)
    with pytest.raises(ValueError, match="must not be finalized"):
        _finalize(plan=empty, artifacts=[])


def test_qualified_id_grammar_allows_hyphens_and_underscores() -> None:
    assert _finalizer().id == "rendering.ffmpeg-finalizer"
    assert replace(_finalizer(), id="1render.2-finalizer",
                   support_decision=_support("1render.2-finalizer")).id == "1render.2-finalizer"
    assert replace(_finalizer(), id="rendering.legacy_hybrid",
                   support_decision=_support("rendering.legacy_hybrid")).id == "rendering.legacy_hybrid"
    assert replace(_finalizer(), id="acme.bad_id",
                   support_decision=_support("acme.bad_id")).id == "acme.bad_id"
    for invalid in (
        "Rendering.Ffmpeg",
        "rendering.-finalizer",
        "unqualified",
    ):
        with pytest.raises(ValueError, match="qualified id"):
            replace(_finalizer(), id=invalid, support_decision=_support(invalid))


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
