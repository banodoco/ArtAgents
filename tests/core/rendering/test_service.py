from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from astrid.core.pack.alias_resolver import AliasResolver
from astrid.core.pack.override import OverrideStore
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    Attachment,
    AudioOwnership,
    FinalizerManifest,
    FinalizerResolution,
    FrameWindow,
    LayerRef,
    PlannerManifest,
    PlannerResolution,
    RendererManifest,
    RendererResolution,
    RenderPlan,
    RenderProfile,
    RenderRequest,
    RenderResult,
    RenderSegment,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.errors import (
    RendererInternalError,
    RendererInvalidArtifactError,
    RendererProtocolError,
    RendererUnsupportedError,
    raise_internal_error,
)
from astrid.core.rendering.publication import publish_render_result
from astrid.core.rendering.registry import (
    ExecutionEligibility,
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
    RenderingCandidate,
    load_default_registries,
)
from astrid.core.rendering.service import RenderService


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _profile(*, audio: bool = False) -> RenderProfile:
    return RenderProfile(
        width=160,
        height=90,
        fps_rational=(10, 1),
        time_base=(1, 10240),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
    )


def _support(
    backend: str,
    *,
    supported: bool = True,
    alternatives: list[str] | None = None,
) -> SupportReport:
    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=supported,
        reasons=[] if supported else ["fixture timeline is unsupported"],
        features={"fixture": True},
        alternatives=list(alternatives or []),
        backend=backend,
        backend_version="1.0.0",
    )


def _candidate(
    root: Path,
    capability_id: str,
    kind: str,
    *,
    eligible: bool = True,
    operations: tuple[str, ...] | None = None,
    capabilities: dict[str, Any] | None = None,
    priority_index: int = 0,
) -> RenderingCandidate[Any]:
    common = dict(
        schema_version=SCHEMA_VERSION,
        id=capability_id,
        name=capability_id,
        version="1.0.0",
        protocol_version=SCHEMA_VERSION,
        command=("fixture-command",),
        required_permissions=(),
        required_binaries=(),
    )
    if kind == "renderer":
        manifest = RendererManifest(
            **common,
            operations=operations or ("render", "support"),
            capabilities=(
                {"supports_windows": True}
                if capabilities is None
                else capabilities
            ),
        )
    elif kind == "planner":
        manifest = PlannerManifest(
            **common,
            operations=operations or ("plan", "support"),
            capabilities=(
                {"supports_fallback": True}
                if capabilities is None
                else capabilities
            ),
        )
    else:
        manifest = FinalizerManifest(
            **common,
            operations=operations or ("finalize", "support"),
            capabilities=(
                {"preserves_attachments": True}
                if capabilities is None
                else capabilities
            ),
        )
    manifest_path = root / f"{capability_id}.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("fixture\n", encoding="utf-8")
    return RenderingCandidate(
        manifest=manifest,
        source_kind="source",
        pack_id=capability_id.split(".", 1)[0],
        pack_root=root,
        manifest_path=manifest_path,
        manifest_digest=_digest(capability_id),
        priority_index=priority_index,
        eligibility=ExecutionEligibility(
            eligible=eligible,
            reason="fixture trust" if eligible else "trust denied",
            trust_method="test" if eligible else None,
        ),
    )


def _renderer_resolution(backend: str) -> RendererResolution:
    return RendererResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest=_digest(backend),
        alias_chain=[],
        override=None,
        support_decision=_support(backend),
        trust_eligibility={"eligible": True},
    )


def _planner_resolution(backend: str = "rendering.legacy_hybrid") -> PlannerResolution:
    return PlannerResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest=_digest(backend),
        trust_eligibility={"eligible": True},
        support_decision=_support(backend),
    )


def _finalizer_resolution(
    backend: str = "rendering.ffmpeg-finalizer",
) -> FinalizerResolution:
    return FinalizerResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest=_digest(backend),
        trust_eligibility={"eligible": True},
        support_decision=_support(backend),
    )


def _plan(
    renderer: str,
    *,
    segment_frames: tuple[int, ...] = (10,),
) -> RenderPlan:
    cursor = 0
    segments: list[RenderSegment] = []
    for duration in segment_frames:
        segments.append(
            RenderSegment(
                window=FrameWindow(
                    start_frame=cursor,
                    end_frame=cursor + duration,
                    fps_rational=(10, 1),
                ),
                renderer=_renderer_resolution(renderer),
                input_hashes={},
            )
        )
        cursor += duration
    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest="0" * 64,
        requested_policy="hybrid",
        planner=_planner_resolution(),
        segments=segments,
        finalizer=_finalizer_resolution(),
        profile=_profile(),
        total_frames=cursor,
        reasons={str(index): "fixture" for index in range(len(segments))},
    )


def _attachment_file(
    workspace: Path,
    name: str,
    data: bytes,
    *,
    kind: str = "fixture",
) -> Attachment:
    att_dir = workspace / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)
    path = att_dir / name
    path.write_bytes(data)
    return Attachment.from_file(
        name=name,
        path=path,
        kind=kind,
        workspace_root=workspace,
    )


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.support: dict[str, SupportReport] = {}
        self.plan: RenderPlan | None = None
        self.fail_render: str | None = None
        self.fail_support: str | None = None
        self.fail_finalize: str | None = None
        self.render_frames: dict[str, int] = {}
        self.render_ownership: dict[str, AudioOwnership] = {}
        self.render_attachments: dict[
            str, dict[str, bytes] | list[dict[str, bytes]]
        ] = {}
        self.finalize_attachments: dict[str, bytes] = {}
        self.finalize_ownership: AudioOwnership = AudioOwnership.NONE
        self.payloads: list[tuple[str, str, dict[str, Any]]] = []

    def run(
        self,
        verb: str,
        command: Any,
        *,
        backend: str,
        request_path: Path,
        result_path: Path,
        cwd: Path,
        **kwargs: Any,
    ) -> Any:
        del command, result_path, cwd, kwargs
        self.calls.append((verb, backend))
        payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
        self.payloads.append((verb, backend, payload))
        workspace = Path(request_path).parent
        if verb == "support":
            if self.fail_support == backend:
                (workspace / "partial.tmp").write_bytes(b"partial")
                raise_internal_error(
                    backend=backend,
                    message="fixture support crashed",
                    recovery_command="retry fixture support",
                )
            return self.support.get(backend, _support(backend))
        if verb == "plan":
            assert self.plan is not None
            return self.plan
        if verb == "render" and self.fail_render == backend:
            (workspace / "partial.tmp").write_bytes(b"partial")
            raise_internal_error(
                backend=backend,
                message="fixture renderer crashed",
                recovery_command="retry fixture renderer",
            )
        output = workspace / "outputs" / payload["output_name"]
        output.parent.mkdir(parents=True, exist_ok=True)
        if verb == "finalize":
            if self.fail_finalize == backend:
                (workspace / "partial.tmp").write_bytes(b"partial")
                raise_internal_error(
                    backend=backend,
                    message="fixture finalizer crashed",
                    recovery_command="retry fixture finalizer",
                )
            frames = payload["plan"]["total_frames"]
            ownership = self.finalize_ownership
            plan_profile = RenderProfile.from_dict(payload["plan"]["profile"])
            if plan_profile.has_audio is (ownership is AudioOwnership.RENDERED):
                profile = plan_profile
            else:
                profile = _profile(audio=ownership is AudioOwnership.RENDERED)
            attachments: dict[str, Attachment] = {}
            for artifact in payload.get("artifacts", []):
                for name, descriptor in (artifact.get("attachments") or {}).items():
                    attachments[name] = Attachment.from_dict(descriptor)
            for name, data in self.finalize_attachments.items():
                attachments[name] = _attachment_file(workspace, name, data)
        else:
            window = payload.get("window")
            frames = (
                self.render_frames[backend]
                if backend in self.render_frames
                else (
                    window["end_frame"] - window["start_frame"]
                    if window is not None
                    else 10
                )
            )
            ownership = self.render_ownership.get(
                backend,
                AudioOwnership(payload.get("audio") or "none"),
            )
            profile = _profile(audio=ownership is AudioOwnership.RENDERED)
            if window is not None:
                # Planned segments are validated against the canonical plan
                # profile; the simulated artifact must speak the window FPS.
                profile = replace(
                    profile, fps_rational=tuple(window["fps_rational"])
                )
            raw_attachments = self.render_attachments.get(backend, {})
            if isinstance(raw_attachments, list):
                # Per-invocation sequence: one attachment map per render call.
                named = raw_attachments.pop(0) if raw_attachments else {}
            else:
                named = raw_attachments
            attachments = {
                name: _attachment_file(workspace, name, data)
                for name, data in named.items()
            }
        output.write_bytes(f"{verb}:{backend}:{frames}".encode())
        video = VideoArtifact.from_file(
            path=output,
            workspace_root=workspace,
            profile=profile,
            duration_frames=frames,
            audio=ownership,
            attachments=attachments,
        )
        return RenderResult(
            schema_version=SCHEMA_VERSION,
            video=video,
            audio_ownership=ownership,
            backend_fragments={backend: {"fixture_backend": backend}},
        )


def _request(tmp_path: Path, *, audio: AudioOwnership | None = None) -> RenderRequest:
    timeline = tmp_path / "timeline.json"
    assets = tmp_path / "assets.json"
    timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")
    assets.write_text('{"assets": {}}', encoding="utf-8")
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline),
        assets_registry_path=str(assets),
        output_name="video.mp4",
        audio=audio,
    )


def _service(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    renderer_ids: tuple[str, ...] = (
        "rendering.remotion",
        "rendering.ffmpeg",
    ),
    planner_ids: tuple[str, ...] = (),
    stage_observer: Any = None,
    audio_completer: Any = None,
    renderer_registry: RendererRegistry | None = None,
    validator: Any = None,
    publisher: Any = None,
    finalizer_id: str | None = None,
) -> RenderService:
    renderers = renderer_registry or RendererRegistry(
        [_candidate(tmp_path, item, "renderer") for item in renderer_ids]
    )
    planners = PlannerRegistry(
        [_candidate(tmp_path, item, "planner") for item in planner_ids]
    )
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
    )
    return RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=validator or (lambda result, **_kwargs: result),
        publisher=publisher or publish_render_result,
        stage_observer=stage_observer,
        audio_completer=audio_completer,
        finalizer_id=finalizer_id,
    )


def test_full_qualified_remotion_render_observes_frozen_service_order(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    calls: list[str] = []

    def validate(result: RenderResult, **_kwargs: Any) -> RenderResult:
        calls.append("validator")
        return result

    def publish(*args: Any, **kwargs: Any) -> Path:
        calls.append("publisher")
        return publish_render_result(*args, **kwargs)

    service = _service(
        tmp_path,
        transport,
        stage_observer=lambda stage, _details: calls.append(stage),
        validator=validate,
        publisher=publish,
    )
    output = tmp_path / "published" / "video.mp4"

    result = service.render_request(
        _request(tmp_path),
        selector="rendering.remotion",
        out_path=output,
    )

    assert result == output
    assert transport.calls == [
        ("support", "rendering.remotion"),
        ("render", "rendering.remotion"),
    ]
    assert calls == [
        "selection",
        "alias",
        "override",
        "winner",
        "eligibility",
        "support",
        "invoke",
        "validate",
        "validator",
        "audio",
        "publish",
        "publisher",
    ]
    assert output.is_file()
    assert Path(f"{output}.provenance.json").is_file()


def test_qualified_ffmpeg_is_strict(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)

    service.render_request(
        _request(tmp_path),
        selector="rendering.ffmpeg",
        out_path=tmp_path / "strict.mp4",
    )

    assert transport.calls == [
        ("support", "rendering.ffmpeg"),
        ("render", "rendering.ffmpeg"),
    ]


def test_direct_renderer_does_not_require_an_executable_finalizer(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    renderers = RendererRegistry(
        [_candidate(tmp_path, "fixture.direct", "renderer")]
    )
    service = RenderService(
        registries=(renderers, PlannerRegistry(), FinalizerRegistry()),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )

    output = service.render_request(
        _request(tmp_path),
        selector="fixture.direct",
        out_path=tmp_path / "direct.mp4",
    )

    assert output.is_file()
    assert transport.calls == [
        ("support", "fixture.direct"),
        ("render", "fixture.direct"),
    ]


@pytest.mark.skip(reason="retired shorthand and fallback route")
def test_legacy_remotion_auto_routes_supported_media_to_ffmpeg_with_warning(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)

    with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
        service.render_request(
            _request(tmp_path),
            selector="remotion",
            out_path=tmp_path / "legacy-remotion.mp4",
        )

    assert ("render", "rendering.ffmpeg") in transport.calls
    assert ("render", "rendering.remotion") not in transport.calls


@pytest.mark.skip(reason="retired shorthand and fallback route")
def test_legacy_remotion_falls_back_when_ffmpeg_declines_support(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.support["rendering.ffmpeg"] = _support(
        "rendering.ffmpeg",
        supported=False,
        alternatives=["rendering.remotion"],
    )
    service = _service(tmp_path, transport)

    service.render_request(
        _request(tmp_path),
        selector="remotion",
        out_path=tmp_path / "legacy-remotion-fallback.mp4",
    )

    assert transport.calls == [
        ("support", "rendering.ffmpeg"),
        ("support", "rendering.remotion"),
        ("render", "rendering.remotion"),
    ]
    payload = _sidecar(tmp_path / "legacy-remotion-fallback.mp4")
    routing = payload["routing"]
    reason = routing["segment_reasons"]["0"]
    assert "rendering.ffmpeg" in reason
    assert "rejected" in reason


@pytest.mark.skip(reason="retired shorthand selector")
def test_legacy_ffmpeg_is_strict(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)

    service.render_request(
        _request(tmp_path),
        selector="ffmpeg",
        out_path=tmp_path / "legacy-ffmpeg.mp4",
    )

    assert transport.calls == [
        ("support", "rendering.ffmpeg"),
        ("render", "rendering.ffmpeg"),
    ]


@pytest.mark.skip(reason="retired built-in planner")
def test_hybrid_selects_planner_and_executes_its_segment(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window")
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )

    service.render_request(
        _request(tmp_path),
        selector="hybrid",
        out_path=tmp_path / "hybrid.mp4",
    )

    assert transport.calls[:2] == [
        ("support", "rendering.legacy_hybrid"),
        ("plan", "rendering.legacy_hybrid"),
    ]
    assert ("render", "fixture.window") in transport.calls
    # The plan pins the ffmpeg finalizer; even a single-segment hybrid plan
    # runs it (profile/audio normalization is the finalizer's contract).
    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls


@pytest.mark.skip(reason="retired built-in planner")
def test_planned_window_is_materialized_for_full_timeline_renderer(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.full")
    renderers = RendererRegistry(
        [
            _candidate(
                tmp_path,
                "fixture.full",
                "renderer",
                capabilities={
                    "supports_full_timeline": True,
                    "supports_windows": False,
                },
            )
        ]
    )
    planners = PlannerRegistry(
        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
    )
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
    )
    service = RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )
    output = tmp_path / "materialized-window.mp4"
    request = _request(tmp_path)

    service.render_request(request, selector="hybrid", out_path=output)

    renderer_payloads = [
        payload
        for verb, backend, payload in transport.payloads
        if backend == "fixture.full" and verb in {"support", "render"}
    ]
    assert len(renderer_payloads) == 2
    assert all(payload["window"] is None for payload in renderer_payloads)
    assert all(
        payload["timeline_path"] != request.timeline_path
        for payload in renderer_payloads
    )
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    assert "materialized_timeline" in sidecar["segments_v2"][0]["input_hashes"]


@pytest.mark.skip(reason="retired built-in planner")
def test_planned_segment_duration_mismatch_is_rejected(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window")
    transport.render_frames["fixture.window"] = 3
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "wrong-duration.mp4"

    with pytest.raises(RendererInvalidArtifactError, match="planned frame window"):
        service.render_request(_request(tmp_path), selector="hybrid", out_path=output)

    assert not output.exists()
    assert not list(tmp_path.glob(".wrong-duration.mp4.render-service-*"))


def test_unknown_backend_is_structured_and_lists_alternatives(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="missing.renderer",
            out_path=tmp_path / "missing.mp4",
        )

    assert caught.value.error.kind == "unsupported"
    assert "rendering.remotion" in caught.value.error.details["alternatives"]
    assert caught.value.error.recovery_command


def test_alias_then_override_changes_resolved_winner(tmp_path: Path) -> None:
    alias = AliasResolver()
    alias.register_alias("acme.alias", "acme.original")
    overrides = OverrideStore(tmp_path / "override-project")
    overrides.set_override("renderer", "acme.original", "acme.winner")
    renderers = RendererRegistry(
        [_candidate(tmp_path, "acme.winner", "renderer")],
        alias_resolver=alias,
        override_store=overrides,
    )
    transport = FakeTransport()
    service = _service(
        tmp_path,
        transport,
        renderer_ids=(),
        renderer_registry=renderers,
    )
    output = tmp_path / "alias.mp4"

    service.render_request(
        _request(tmp_path), selector="acme.alias", out_path=output
    )

    assert ("render", "acme.winner") in transport.calls
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    resolution = sidecar["segments_v2"][0]["renderer"]
    assert resolution["alias_chain"] == ["acme.alias", "acme.original"]
    assert resolution["override"] == {
        "from": "acme.original",
        "to": "acme.winner",
    }


def test_execution_ineligible_candidate_is_denied(tmp_path: Path) -> None:
    renderers = RendererRegistry(
        [_candidate(tmp_path, "denied.renderer", "renderer", eligible=False)]
    )
    transport = FakeTransport()
    service = _service(
        tmp_path,
        transport,
        renderer_ids=(),
        renderer_registry=renderers,
    )

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="denied.renderer",
            out_path=tmp_path / "denied.mp4",
        )

    registry_error = caught.value.error.details["registry_error"]
    assert registry_error["code"] == "execution_ineligible"
    assert transport.calls == []


def test_unsupported_support_report_is_structured_with_reported_alternative(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.support["rendering.ffmpeg"] = _support(
        "rendering.ffmpeg",
        supported=False,
        alternatives=["rendering.remotion"],
    )
    service = _service(tmp_path, transport)

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="rendering.ffmpeg",
            out_path=tmp_path / "unsupported.mp4",
        )

    assert caught.value.error.details["alternatives"] == ["rendering.remotion"]
    assert caught.value.error.details["reasons"] == [
        "fixture timeline is unsupported"
    ]


def test_renderer_without_support_operation_fails_closed_on_missing_hints(
    tmp_path: Path,
) -> None:
    renderers = RendererRegistry(
        [
            _candidate(
                tmp_path,
                "fixture.static",
                "renderer",
                operations=("render",),
                capabilities={},
            )
        ]
    )
    transport = FakeTransport()
    service = RenderService(
        registries=(renderers, PlannerRegistry(), FinalizerRegistry()),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="fixture.static",
            out_path=tmp_path / "static.mp4",
        )

    assert "full timelines" in " ".join(caught.value.error.details["reasons"])
    assert transport.calls == []


@pytest.mark.parametrize(
    "ownership", [AudioOwnership.PASSTHROUGH, AudioOwnership.NONE]
)
def test_host_audio_completion_handles_visual_only_modes(
    tmp_path: Path,
    ownership: AudioOwnership,
) -> None:
    transport = FakeTransport()
    completed: list[AudioOwnership] = []

    def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
        completed.append(result.audio_ownership)
        if result.audio_ownership is AudioOwnership.PASSTHROUGH:
            return replace(
                result,
                video=replace(
                    result.video,
                    profile=_profile(audio=True),
                    audio=AudioOwnership.RENDERED,
                ),
                audio_ownership=AudioOwnership.RENDERED,
            )
        return result

    service = _service(tmp_path, transport, audio_completer=audio_completer)
    output = tmp_path / f"{ownership.value}.mp4"

    service.render_request(
        _request(tmp_path, audio=ownership),
        selector="rendering.ffmpeg",
        out_path=output,
    )

    assert completed == [ownership]
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    expected = (
        AudioOwnership.RENDERED
        if ownership is AudioOwnership.PASSTHROUGH
        else AudioOwnership.NONE
    )
    assert sidecar["audio_ownership"] == expected.value


def test_passthrough_audio_cannot_publish_without_host_completion(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "incomplete-passthrough.mp4"

    with pytest.raises(RendererUnsupportedError, match="audio completer"):
        service.render_request(
            _request(tmp_path, audio=AudioOwnership.PASSTHROUGH),
            selector="rendering.ffmpeg",
            out_path=output,
        )

    assert not output.exists()
    assert not Path(f"{output}.provenance.json").exists()


@pytest.mark.skip(reason="retired built-in planner")
def test_multiple_segments_run_registered_finalizer(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "finalized.mp4"

    service.render_request(
        _request(tmp_path), selector="hybrid", out_path=output
    )

    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    assert output.read_bytes().startswith(b"finalize:rendering.ffmpeg-finalizer")


@pytest.mark.skip(reason="retired built-in planner")
def test_multiple_segments_defer_audio_completion_until_after_finalizer(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    transport.render_ownership["fixture.window"] = AudioOwnership.PASSTHROUGH
    transport.finalize_ownership = AudioOwnership.PASSTHROUGH
    completions: list[str] = []

    def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
        completions.append(result.video.path)
        return replace(
            result,
            video=replace(
                result.video,
                profile=_profile(audio=True),
                audio=AudioOwnership.RENDERED,
            ),
            audio_ownership=AudioOwnership.RENDERED,
        )

    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
        audio_completer=audio_completer,
    )
    output = tmp_path / "finalized-passthrough.mp4"

    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)

    assert completions == ["outputs/video.mp4"]
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    assert sidecar["audio_ownership"] == AudioOwnership.RENDERED.value


@pytest.mark.skip(reason="retired built-in planner")
def test_multiple_segments_allow_finalizer_to_complete_silent_audio_segment(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.plan = replace(
        _plan("fixture.window", segment_frames=(5, 5)),
        profile=_profile(audio=True),
    )
    transport.render_ownership["fixture.window"] = AudioOwnership.NONE
    transport.finalize_ownership = AudioOwnership.RENDERED
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "finalized-silence.mp4"
    request = replace(
        _request(tmp_path),
        audio=AudioOwnership.RENDERED,
        profile=_profile(audio=True),
    )

    service.render_request(request, selector="hybrid", out_path=output)

    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    assert sidecar["audio_ownership"] == AudioOwnership.RENDERED.value


def test_backend_failure_removes_invocation_workspace_and_commits_nothing(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.fail_render = "rendering.ffmpeg"
    service = _service(tmp_path, transport)
    output = tmp_path / "failed.mp4"

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=output
        )

    assert not output.exists()
    assert not Path(f"{output}.provenance.json").exists()
    assert not list(tmp_path.glob(".failed.mp4.render-service-*"))


def test_each_success_commits_exactly_one_sidecar(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "one-sidecar.mp4"

    service.render_request(
        _request(tmp_path), selector="rendering.ffmpeg", out_path=output
    )

    sidecars = list(tmp_path.glob("*.provenance.json"))
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["output"] == str(output)
    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# T4.5 — routing / hybrid matrix
# ---------------------------------------------------------------------------


def _sidecar(output: Path) -> dict[str, Any]:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


def _hybrid_timeline(*, fps: int = 24) -> dict[str, Any]:
    """A media clip plus an overlapping text-card: simple/complex/simple windows."""
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": fps}}
        },
        "tracks": [
            {"id": "v", "kind": "visual"},
            {"id": "a", "kind": "audio"},
        ],
        "clips": [
            {
                "id": "media",
                "at": 0,
                "track": "v",
                "clipType": "media",
                "asset": "source",
                "from": 0,
                "to": 6,
                "speed": 1,
                "volume": 0,
            },
            {
                "id": "title",
                "at": 2,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ],
    }


def _hybrid_request(
    tmp_path: Path,
    timeline: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    audio: AudioOwnership | None = None,
) -> RenderRequest:
    root = tmp_path / "media"
    root.mkdir(exist_ok=True)
    timeline_path = root / "timeline.json"
    assets_path = root / "assets.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    assets_path.write_text(json.dumps({"assets": {}}), encoding="utf-8")
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name="video.mp4",
        audio=audio,
        backend_config=(
            {} if config is None else {"rendering.legacy_hybrid": config}
        ),
    )


def _planner_support_resolver(
    accepted: set[str] | None = None,
):
    supported = (
        {"raw_command.renderer", "rendering.remotion", "rendering.ffmpeg"}
        if accepted is None
        else accepted
    )

    def resolve(
        renderer_id: str, _request: RenderRequest, _timeline: object
    ) -> SupportReport:
        ok = renderer_id in supported
        return SupportReport(
            schema_version=SCHEMA_VERSION,
            supported=ok,
            reasons=[] if ok else ["fixture rejection"],
            features={"fixture": True},
            alternatives=[],
            backend=renderer_id,
            backend_version="1.0.0",
        )

    return resolve


def _mixed_plan(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    config: dict[str, Any],
) -> RenderRequest:
    timeline = _hybrid_timeline()
    request = _hybrid_request(tmp_path, timeline, config=config)
    transport.plan = legacy_hybrid.plan(
        request,
        workspace=tmp_path,
        support_resolver=_planner_support_resolver(),
    )
    return request


def _mixed_service(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    renderer_ids: tuple[str, ...] = (
        "raw_command.renderer",
        "rendering.remotion",
    ),
) -> RenderService:
    renderers = RendererRegistry(
        [_candidate(tmp_path, item, "renderer") for item in renderer_ids]
    )
    planners = PlannerRegistry(
        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
    )
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
    )
    return RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )


RAW_FIXTURE_PACK_ROOT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "renderer_packs"
    / "raw_command"
)


class _RawFixtureTransport(FakeTransport):
    """FakeTransport that executes the deterministic Batch-2 raw fixture.

    ``raw_command.renderer`` invocations run the fixture's real stdlib
    ``backend.py`` subprocess; every other backend stays simulated.
    """

    def __init__(self, pack_root: Path = RAW_FIXTURE_PACK_ROOT) -> None:
        super().__init__()
        self.pack_root = Path(pack_root)

    def run(
        self,
        verb: str,
        command: Any,
        *,
        backend: str,
        request_path: Path,
        result_path: Path,
        cwd: Path,
        **kwargs: Any,
    ) -> Any:
        if backend != "raw_command.renderer":
            return super().run(
                verb,
                command,
                backend=backend,
                request_path=request_path,
                result_path=result_path,
                cwd=cwd,
                **kwargs,
            )
        self.calls.append((verb, backend))
        subprocess.run(
            [
                sys.executable,
                "backend.py",
                verb,
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ],
            cwd=self.pack_root,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if verb == "support":
            return SupportReport.from_dict(payload)
        if verb == "render":
            return RenderResult.from_dict(payload)
        raise AssertionError(f"raw fixture backend has no {verb!r} verb")


@pytest.mark.parametrize(
    (
        "selector",
        "hybrid_plan",
        "expected_calls",
        "expected_engine",
        "expected_backend",
        "auto_route",
        "warning",
    ),
    [
        (
            "rendering.remotion",
            False,
            [("support", "rendering.remotion"), ("render", "rendering.remotion")],
            "rendering.remotion",
            "rendering.remotion",
            False,
            False,
        ),
        (
            "rendering.ffmpeg",
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "rendering.ffmpeg",
            "rendering.ffmpeg",
            False,
            False,
        ),
        (
            "remotion",
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "remotion",
            "rendering.ffmpeg",
            True,
            True,
        ),
        (
            None,
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "remotion",
            "rendering.ffmpeg",
            True,
            True,
        ),
        (
            "ffmpeg",
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "ffmpeg",
            "rendering.ffmpeg",
            False,
            False,
        ),
        (
            "hybrid",
            True,
            [
                ("support", "rendering.legacy_hybrid"),
                ("plan", "rendering.legacy_hybrid"),
                ("support", "fixture.window"),
                ("render", "fixture.window"),
                ("support", "rendering.ffmpeg-finalizer"),
                ("finalize", "rendering.ffmpeg-finalizer"),
            ],
            "hybrid",
            "fixture.window",
            False,
            False,
        ),
    ],
    ids=[
        "qualified-remotion",
        "qualified-ffmpeg",
        "legacy-remotion",
        "default-remotion",
        "legacy-ffmpeg",
        "hybrid",
    ],
)
@pytest.mark.skip(reason="retired shorthand and planner selectors")
def test_selector_routing_matrix(
    tmp_path: Path,
    selector: str | None,
    hybrid_plan: bool,
    expected_calls: list[tuple[str, str]],
    expected_engine: str,
    expected_backend: str,
    auto_route: bool,
    warning: bool,
) -> None:
    transport = FakeTransport()
    if hybrid_plan:
        transport.plan = _plan("fixture.window")
        service = _service(
            tmp_path,
            transport,
            renderer_ids=("fixture.window",),
            planner_ids=("rendering.legacy_hybrid",),
        )
    else:
        service = _service(tmp_path, transport)
    output = tmp_path / "routing.mp4"

    if warning:
        with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
            service.render_request(
                _request(tmp_path), selector=selector, out_path=output
            )
    else:
        service.render_request(
            _request(tmp_path), selector=selector, out_path=output
        )

    assert transport.calls == expected_calls
    if selector != "hybrid":
        assert not any(verb == "finalize" for verb, _backend in transport.calls)
    payload = _sidecar(output)
    routing = payload["routing"]
    assert routing["requested_engine"] == expected_engine
    assert routing["requested_policy"] == expected_engine
    assert routing["resolved_backend"] == expected_backend
    assert routing["resolved_backends"] == [expected_backend]
    assert routing["auto_route"] is auto_route
    assert payload["requested_policy"] == expected_engine


def test_trust_denied_higher_priority_candidate_never_wins(
    tmp_path: Path,
) -> None:
    renderers = RendererRegistry(
        [
            _candidate(
                tmp_path,
                "contested.renderer",
                "renderer",
                eligible=False,
                priority_index=0,
            ),
            _candidate(
                tmp_path,
                "contested.renderer",
                "renderer",
                eligible=True,
                priority_index=10,
            ),
        ]
    )
    transport = FakeTransport()
    service = _service(
        tmp_path,
        transport,
        renderer_ids=(),
        renderer_registry=renderers,
    )
    output = tmp_path / "contested.mp4"

    service.render_request(
        _request(tmp_path), selector="contested.renderer", out_path=output
    )

    assert transport.calls == [
        ("support", "contested.renderer"),
        ("render", "contested.renderer"),
    ]
    payload = _sidecar(output)
    renderer = payload["segments_v2"][0]["renderer"]
    assert renderer["id"] == "contested.renderer"
    assert renderer["trust_eligibility"]["eligible"] is True
    assert renderer["trust_eligibility"]["reason"] == "fixture trust"


def test_alias_and_override_to_trust_denied_only_target_is_structured(
    tmp_path: Path,
) -> None:
    alias = AliasResolver()
    alias.register_alias("acme.alias", "acme.original")
    overrides = OverrideStore(tmp_path / "override-project")
    overrides.set_override("renderer", "acme.original", "acme.denied")
    renderers = RendererRegistry(
        [_candidate(tmp_path, "acme.denied", "renderer", eligible=False)],
        alias_resolver=alias,
        override_store=overrides,
    )
    transport = FakeTransport()
    service = _service(
        tmp_path,
        transport,
        renderer_ids=(),
        renderer_registry=renderers,
    )

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="acme.alias",
            out_path=tmp_path / "denied.mp4",
        )

    registry_error = caught.value.error.details["registry_error"]
    assert registry_error["code"] == "execution_ineligible"
    assert transport.calls == []
    assert not list(tmp_path.glob("*.provenance.json"))


@pytest.mark.skip(reason="retired shorthand selector")
def test_unknown_short_selector_lists_legacy_alternatives(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="webgl",
            out_path=tmp_path / "webgl.mp4",
        )

    error = caught.value.error
    assert error.kind == "unsupported"
    assert error.details["legacy_selectors"] == ["remotion", "ffmpeg", "hybrid"]
    assert "remotion" in error.recovery_command
    assert transport.calls == []


@pytest.mark.parametrize(
    "name",
    [
        "a/b.mp4",
        "a\\b.mp4",
        "sub/out.mp4",
        "/abs.mp4",
        "../evil.mp4",
        "..mp4",
        "..",
        ".",
        "",
    ],
)
def test_separator_and_traversal_output_names_are_rejected_before_invocation(
    tmp_path: Path, name: str
) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "never-written.mp4"
    request = _request(tmp_path).to_dict()
    request["output_name"] = name

    with pytest.raises(RendererProtocolError) as caught:
        service.render_request(request, selector="rendering.ffmpeg", out_path=output)

    assert caught.value.error.kind == "protocol"
    assert caught.value.error.recovery_command
    assert transport.calls == []
    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_facade_delegates_suffix_policy_but_preserves_hype_default() -> None:
    from astrid.packs.rendering.executors.render.run import (
        DEFAULT_OUTPUT_NAME,
        validate_output_name,
    )

    assert DEFAULT_OUTPUT_NAME == "hype.mp4"
    assert validate_output_name("hype.mp4") == "hype.mp4"
    assert validate_output_name("out.mov") == "out.mov"


def test_hype_mp4_default_output_name_is_preserved(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "published" / "hype.mp4"
    request = replace(_request(tmp_path), output_name="hype.mp4")

    service.render_request(
        request, selector="rendering.ffmpeg", out_path=output
    )

    render_payloads = [
        payload
        for verb, backend, payload in transport.payloads
        if verb == "render" and backend == "rendering.ffmpeg"
    ]
    assert len(render_payloads) == 1
    assert render_payloads[0]["output_name"] == "hype.mp4"
    payload = _sidecar(output)
    assert payload["output"] == str(output.resolve())
    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    (
        "selector",
        "plan_segments",
        "backend_config",
        "expect_finalize",
        "expected_engine",
    ),
    [
        ("rendering.remotion", None, {}, False, "rendering.remotion"),
        ("rendering.ffmpeg", None, {}, False, "rendering.ffmpeg"),
        (
            "rendering.ffmpeg",
            None,
            {"rendering.ffmpeg": {"mode": "optimized", "stream_copy": True}},
            False,
            "rendering.ffmpeg",
        ),
        (
            "rendering.ffmpeg",
            None,
            {"rendering.ffmpeg": {"audio_reactive": True}},
            False,
            "rendering.ffmpeg",
        ),
    ],
    ids=[
        "remotion",
        "ffmpeg",
        "ffmpeg-optimized",
        "ffmpeg-audio-reactive",
    ],
)
def test_builtin_paths_commit_exactly_one_video_and_sidecar(
    tmp_path: Path,
    selector: str,
    plan_segments: tuple[int, ...] | None,
    backend_config: dict[str, dict[str, Any]],
    expect_finalize: bool,
    expected_engine: str,
) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "builtin.mp4"
    request = replace(_request(tmp_path), backend_config=backend_config)

    service.render_request(request, selector=selector, out_path=output)

    assert output.is_file()
    sidecars = list(tmp_path.glob("*.provenance.json"))
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert payload["output"] == str(output.resolve())
    assert payload["engine"] == expected_engine
    assert payload["audio_ownership"] == "none"
    for _verb, backend, payload_data in transport.payloads:
        if backend in backend_config:
            assert payload_data["backend_config"][backend] == backend_config[backend]
    if expect_finalize:
        assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    else:
        assert not any(verb == "finalize" for verb, _backend in transport.calls)
    assert not list(tmp_path.glob(".*.render-service-*"))


@pytest.mark.skip(reason="retired built-in planner")
def test_raw_mixed_plan_routes_windows_and_aligns_segment_provenance(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    request = _mixed_plan(
        tmp_path,
        transport,
        config={
            "simple_renderers": ["raw_command.renderer"],
            "complex_renderers": ["rendering.remotion"],
        },
    )
    service = _mixed_service(tmp_path, transport)
    output = tmp_path / "mixed.mp4"

    service.render_request(request, selector="hybrid", out_path=output)

    render_calls = [backend for verb, backend in transport.calls if verb == "render"]
    assert render_calls == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    payload = _sidecar(output)
    segments = payload["segments_v2"]
    assert [segment["renderer"]["id"] for segment in segments] == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    windows = [
        (segment["window"]["start_frame"], segment["window"]["end_frame"])
        for segment in segments
    ]
    assert windows[0][0] == 0
    assert windows[-1][1] == transport.plan.total_frames
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))
    assert all("timeline" in segment["input_hashes"] for segment in segments)
    assert payload["finalizer"]["id"] == "rendering.ffmpeg-finalizer"
    assert payload["routing"]["requested_engine"] == "hybrid"


@pytest.mark.skip(reason="retired built-in planner")
def test_raw_mixed_plan_executes_deterministic_raw_fixture_window(
    tmp_path: Path,
) -> None:
    transport = _RawFixtureTransport()
    request = _mixed_plan(
        tmp_path,
        transport,
        config={
            "simple_renderers": ["raw_command.renderer"],
            "complex_renderers": ["rendering.remotion"],
        },
    )
    service = _mixed_service(tmp_path, transport)
    output = tmp_path / "mixed-real.mp4"

    service.render_request(request, selector="hybrid", out_path=output)

    render_calls = [backend for verb, backend in transport.calls if verb == "render"]
    assert render_calls == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    payload = _sidecar(output)
    segments = payload["segments_v2"]
    assert [segment["renderer"]["id"] for segment in segments] == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    raw_windows = [
        segment["window"]
        for segment in segments
        if segment["renderer"]["id"] == "raw_command.renderer"
    ]
    assert len(raw_windows) == 2
    assert all(
        segment["window"]["end_frame"] - segment["window"]["start_frame"] > 0
        for segment in segments
    )
    # The raw fixture really rendered its windows: real mp4 bytes with the
    # planned frame count in the committed artifact profile.
    assert output.is_file()
    assert output.read_bytes().startswith(b"finalize:rendering.ffmpeg-finalizer")


@pytest.mark.parametrize(
    ("selector", "plan_segments", "ownership", "expected", "completer"),
    [
        ("rendering.remotion", None, AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
        ("rendering.ffmpeg", None, AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
        ("rendering.remotion", None, AudioOwnership.NONE, AudioOwnership.NONE, False),
        ("rendering.ffmpeg", None, AudioOwnership.NONE, AudioOwnership.NONE, False),
        ("rendering.remotion", None, AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
        ("rendering.ffmpeg", None, AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
        ("hybrid", (10,), AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
        ("hybrid", (10,), AudioOwnership.NONE, AudioOwnership.NONE, False),
        ("hybrid", (10,), AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
    ],
    ids=[
        "remotion-rendered",
        "ffmpeg-rendered",
        "remotion-none",
        "ffmpeg-none",
        "remotion-passthrough",
        "ffmpeg-passthrough",
        "hybrid-rendered",
        "hybrid-none",
        "hybrid-passthrough",
    ],
)
@pytest.mark.skip(reason="retired planner audio matrix")
def test_audio_ownership_matrix_across_backends(
    tmp_path: Path,
    selector: str,
        plan_segments: tuple[int, ...] | None,
    ownership: AudioOwnership,
    expected: AudioOwnership,
    completer: bool,
) -> None:
    transport = FakeTransport()

    def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
        return replace(
            result,
            video=replace(
                result.video,
                profile=_profile(audio=True),
                audio=AudioOwnership.RENDERED,
            ),
            audio_ownership=AudioOwnership.RENDERED,
        )

    if plan_segments is not None:
        transport.plan = _plan("fixture.window", segment_frames=plan_segments)
        service = _service(
            tmp_path,
            transport,
            renderer_ids=("fixture.window",),
            planner_ids=("rendering.legacy_hybrid",),
            audio_completer=audio_completer if completer else None,
        )
        # A pinned planner finalizer completes audio for hybrid plans; the
        # fixture finalizer must honor the ownership the request asked for.
        transport.finalize_ownership = ownership
    else:
        service = _service(
            tmp_path,
            transport,
            audio_completer=audio_completer if completer else None,
        )
    output = tmp_path / f"audio-{ownership.value}.mp4"

    service.render_request(
        replace(_request(tmp_path), audio=ownership),
        selector=selector,
        out_path=output,
    )

    payload = _sidecar(output)
    assert payload["audio_ownership"] == expected.value
    assert payload["routing"]["requested_engine"] == (
        "hybrid" if plan_segments is not None else selector
    )


@pytest.mark.skip(reason="retired built-in planner")
def test_finalizer_failure_removes_workspace_and_commits_nothing(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.fail_finalize = "rendering.ffmpeg-finalizer"
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "failed-finalize.mp4"

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="hybrid", out_path=output
        )

    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_support_failure_removes_workspace_and_commits_nothing(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.fail_support = "rendering.ffmpeg"
    service = _service(tmp_path, transport)
    output = tmp_path / "failed-support.mp4"

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=output
        )

    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_renderer_attachments_survive_validation_into_committed_provenance(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.render_attachments["rendering.ffmpeg"] = {
        "storyboard.png": b"png-bytes",
        "captions.srt": b"srt-bytes",
    }
    service = _service(tmp_path, transport)
    output = tmp_path / "attachments.mp4"

    service.render_request(
        _request(tmp_path), selector="rendering.ffmpeg", out_path=output
    )

    payload = _sidecar(output)
    assert set(payload["attachments"]) == {"storyboard.png", "captions.srt"}
    assert payload["attachments"]["storyboard.png"]["sha256"] == hashlib.sha256(
        b"png-bytes"
    ).hexdigest()
    assert payload["attachments"]["storyboard.png"]["kind"] == "fixture"
    assert payload["attachments"]["storyboard.png"]["path"].endswith(
        "storyboard.png"
    )
    assert len(payload["artifact_profiles"]) == 1
    assert set(payload["artifact_profiles"][0]["attachments"]) == {
        "storyboard.png",
        "captions.srt",
    }


@pytest.mark.skip(reason="retired built-in planner")
def test_finalizer_preserves_segment_attachments_and_adds_its_own(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.render_attachments["fixture.window"] = [
        {"segment-a.txt": b"first-segment"},
        {"segment-b.txt": b"second-segment"},
    ]
    transport.finalize_attachments = {"final-note.txt": b"final"}
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "finalized-attachments.mp4"

    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)

    payload = _sidecar(output)
    assert set(payload["attachments"]) == {
        "segment-a.txt",
        "segment-b.txt",
        "final-note.txt",
    }
    assert len(payload["artifact_profiles"]) == 2
    assert set(payload["artifact_profiles"][0]["attachments"]) == {"segment-a.txt"}
    assert set(payload["artifact_profiles"][1]["attachments"]) == {"segment-b.txt"}


def test_audio_completer_dropping_attachments_is_rejected(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.render_attachments["rendering.ffmpeg"] = {"must-survive.txt": b"x"}

    def bad_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
        return replace(
            result,
            video=replace(
                result.video,
                profile=_profile(audio=True),
                audio=AudioOwnership.RENDERED,
                attachments={},
            ),
            audio_ownership=AudioOwnership.RENDERED,
        )

    service = _service(tmp_path, transport, audio_completer=bad_completer)
    output = tmp_path / "dropped-attachments.mp4"

    with pytest.raises(RendererInvalidArtifactError, match="attachments"):
        service.render_request(
            replace(_request(tmp_path), audio=AudioOwnership.PASSTHROUGH),
            selector="rendering.ffmpeg",
            out_path=output,
        )

    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))


# ---------------------------------------------------------------------------
# Real-backend integration through the generic service (issue-8 coverage)
# ---------------------------------------------------------------------------


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("real FFmpeg smoke dependency is unavailable")


def _real_service(tmp_path: Path) -> RenderService:
    renderers, planners, finalizers = load_default_registries(
        tmp_path
    )
    return RenderService(registries=(renderers, planners, finalizers))


def _real_media_inputs(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "media"
    root.mkdir(exist_ok=True)
    source = root / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x90:r=10:d=0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    timeline_path = root / "timeline.json"
    assets_path = root / "assets.json"
    timeline_path.write_text(
        json.dumps(
            {
                "theme": "banodoco-default",
                "theme_overrides": {
                    "visual": {"canvas": {"width": 160, "height": 90, "fps": 10}}
                },
                "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
                "clips": [
                    {
                        "id": "source",
                        "at": 0,
                        "track": "v",
                        "clipType": "media",
                        "asset": "source",
                        "from": 0,
                        "to": 0.5,
                        "speed": 1,
                        "volume": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assets_path.write_text(
        json.dumps(
            {
                "assets": {
                    "source": {
                        "file": source.name,
                        "type": "video/mp4",
                        "duration": 0.5,
                        "resolution": "160x90",
                        "fps": 10,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return timeline_path, assets_path


def _add_audio_track(timeline_path: Path) -> None:
    """Mux an AAC track into the media source so the whole-media path with
    audio (the canonical 48 kHz contract) is exercised end to end."""
    source = timeline_path.parent / "source.mp4"
    audio_path = source.with_suffix(".aac")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=0.5",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    muxed = timeline_path.parent / "muxed.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(muxed),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    muxed.replace(source)


@pytest.mark.parametrize(
    "media_kind",
    ["plain", "audio"],
    ids=["nominal", "with-audio"],
)
def test_real_ffmpeg_renders_through_generic_service(
    tmp_path: Path,
    media_kind: str,
) -> None:
    """The service drives the real FFmpeg backend end to end: one video and
    one committed sidecar through the real CommandTransport (no fake
    transport), including the whole-media optimized path when the source
    probe supports it."""
    _require_ffmpeg()
    timeline_path, assets_path = _real_media_inputs(tmp_path)
    if media_kind == "audio":
        _add_audio_track(timeline_path)
    service = _real_service(tmp_path)
    output = tmp_path / "real-ffmpeg.mp4"

    service.render_request(
        replace(
            _request(tmp_path),
            timeline_path=str(timeline_path),
            assets_registry_path=str(assets_path),
        ),
        selector="rendering.ffmpeg",
        out_path=output,
    )

    assert output.is_file()
    assert output.stat().st_size > 0
    sidecars = list(tmp_path.glob("*.provenance.json"))
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["output"] == str(output.resolve())
    assert payload["engine"] == "rendering.ffmpeg"


@pytest.mark.skip(reason="retired built-in planner")
def test_real_hybrid_plans_assigns_ffmpeg_and_finalizes_through_service(
    tmp_path: Path,
) -> None:
    """Real hybrid planning: the media-only timeline routes every window to
    the real FFmpeg backend and the real ffmpeg finalizer concatenates."""
    _require_ffmpeg()
    timeline_path, assets_path = _real_media_inputs(tmp_path)
    service = _real_service(tmp_path)
    output = tmp_path / "real-hybrid.mp4"

    service.render_request(
        replace(
            _request(tmp_path),
            timeline_path=str(timeline_path),
            assets_registry_path=str(assets_path),
        ),
        selector="hybrid",
        out_path=output,
    )

    assert output.is_file()
    assert output.stat().st_size > 0
    sidecars = list(tmp_path.glob("*.provenance.json"))
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["routing"]["requested_engine"] == "hybrid"
    resolved = payload["routing"]["resolved_policy"]
    assert resolved["planner"] == "rendering.legacy_hybrid"
    assert resolved["finalizer"] == "rendering.ffmpeg-finalizer"


def _real_audio_reactive_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """A two-clip timeline the strict FFmpeg backend renders through its
    audio-reactive colour specialization (real AAC audio source)."""
    root = tmp_path / "reactive"
    root.mkdir(exist_ok=True)
    audio_path = root / "tone.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=0.5",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    timeline_path = root / "timeline.json"
    assets_path = root / "assets.json"
    timeline_path.write_text(
        json.dumps(
            {
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
                            "events": [
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
        ),
        encoding="utf-8",
    )
    assets_path.write_text(
        json.dumps(
            {
                "assets": {
                    "audio": {
                        "file": str(audio_path),
                        "type": "audio/wav",
                        "duration": 0.5,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return timeline_path, assets_path


def test_real_ffmpeg_audio_reactive_through_generic_service(
    tmp_path: Path,
) -> None:
    """The service drives the real FFmpeg backend through its audio-reactive
    colour specialization end to end (no fake transport)."""
    _require_ffmpeg()
    timeline_path, assets_path = _real_audio_reactive_inputs(tmp_path)
    service = _real_service(tmp_path)
    output = tmp_path / "real-reactive.mp4"

    service.render_request(
        replace(
            _request(tmp_path),
            timeline_path=str(timeline_path),
            assets_registry_path=str(assets_path),
        ),
        selector="rendering.ffmpeg",
        out_path=output,
    )

    assert output.is_file()
    assert output.stat().st_size > 0
    sidecars = list(tmp_path.glob("*.provenance.json"))
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["engine"] == "rendering.ffmpeg"
    assert payload["audio_ownership"] == "rendered"


@pytest.mark.skip(reason="retired built-in planner")
def test_single_segment_plan_records_finalizer_fragment(
    tmp_path: Path,
) -> None:
    """A single-segment plan that pins the ffmpeg finalizer must record BOTH
    the renderer fragment and the executed finalizer fragment in provenance."""
    transport = FakeTransport()
    transport.plan = _plan("fixture.window", segment_frames=(10,))
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "single-finalize.mp4"

    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)

    payload = _sidecar(output)
    fragments = payload["backend_fragments"]
    assert fragments["fixture.window"]["fixture_backend"] == "fixture.window"
    assert (
        fragments["rendering.ffmpeg-finalizer"]["fixture_backend"]
        == "rendering.ffmpeg-finalizer"
    )
    # One hashed lineage entry per segment (the renderer artifact), while the
    # finalizer's artifact is represented by the finalizer fragment.
    assert len(payload["artifact_profiles"]) == 1
    assert payload["artifact_profiles"][0]["path"].endswith("segment-0000.mp4")


# ---------------------------------------------------------------------------
# Layer Stack Batch 2 — track-filtered host slice + alpha metadata stamp.
# _window_timeline slices the host timeline to one z-layer's tracks; the
# layer=None path is unchanged.  _segment_request passes layer.tracks and
# stamps metadata.astrid_layer (alpha = z > 0) into the materialized copy.
# ---------------------------------------------------------------------------


def _layered_timeline(tmp_path: Path) -> Path:
    """Two visual tracks + one audio track, both visuals in window 0..1s.

    v1 and v2 each carry one clip spanning the whole window; ``a1`` exists
    only as a track (no clips), mirroring the existing pruning fixture shape.
    """
    timeline = tmp_path / "layered-timeline.json"
    timeline.write_text(
        json.dumps(
            {
                "tracks": [
                    {"id": "v1", "name": "bottom"},
                    {"id": "v2", "name": "top"},
                    {"id": "a1", "name": "audio"},
                ],
                "clips": [
                    {
                        "id": "c1",
                        "track": "v1",
                        "at": 0.0,
                        "from": 0.0,
                        "to": 10.0,
                    },
                    {
                        "id": "c2",
                        "track": "v2",
                        "at": 0.0,
                        "from": 0.0,
                        "to": 10.0,
                    },
                ],
                "metadata": {"project": "layer-slice", "custom": {"keep": 1}},
            }
        ),
        encoding="utf-8",
    )
    return timeline


def _window(*, start: int = 0, end: int = 10) -> FrameWindow:
    return FrameWindow(start_frame=start, end_frame=end, fps_rational=(10, 1))


def _layered_segment(*, z: int, tracks: tuple[str, ...]) -> RenderSegment:
    return RenderSegment(
        window=_window(),
        renderer=_renderer_resolution("fixture.full"),
        input_hashes={},
        layer=LayerRef(z=z, tracks=tracks),
    )


def _layered_plan(*, z: int, tracks: tuple[str, ...]) -> RenderPlan:
    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest="0" * 64,
        requested_policy="hybrid",
        planner=_planner_resolution(),
        segments=[_layered_segment(z=z, tracks=tracks)],
        finalizer=_finalizer_resolution(),
        profile=_profile(),
        total_frames=10,
        reasons={"0": "fixture"},
    )


def test_window_timeline_allowlist_slices_to_layer_tracks(tmp_path: Path) -> None:
    """A segment on layer z=1 owning only v2 must see ONLY track v2 and its
    clips — never v1's material, even though both overlap the window."""
    timeline = json.loads(_layered_timeline(tmp_path).read_text(encoding="utf-8"))

    materialized = RenderService._window_timeline(
        timeline, _window(), tracks=("v2",)
    )

    assert [track["id"] for track in materialized["tracks"]] == ["v2"]
    assert [clip["id"] for clip in materialized["clips"]] == ["c2_0_10"]


def test_window_timeline_without_allowlist_keeps_existing_pruning(
    tmp_path: Path,
) -> None:
    """layer=None segments keep today's behavior byte-for-byte: tracks with
    in-window clips are kept, track-less-in-window a1 is pruned."""
    timeline = json.loads(_layered_timeline(tmp_path).read_text(encoding="utf-8"))

    materialized = RenderService._window_timeline(timeline, _window())

    assert [track["id"] for track in materialized["tracks"]] == ["v1", "v2"]
    assert {clip["id"] for clip in materialized["clips"]} == {"c1_0_10", "c2_0_10"}


def test_window_timeline_allowlist_track_without_window_clips_stays_present(
    tmp_path: Path,
) -> None:
    """An allowlisted track whose clips all fall outside the window must
    survive pruning: the renderer needs to know its layer exists so it can
    emit background/transparent output for the span."""
    timeline = json.loads(_layered_timeline(tmp_path).read_text(encoding="utf-8"))
    timeline["clips"] = [
        {
            "id": "c2-late",
            "track": "v2",
            "at": 5.0,
            "from": 0.0,
            "to": 10.0,
        }
    ]

    materialized = RenderService._window_timeline(
        timeline, _window(), tracks=("v2",)
    )

    assert [track["id"] for track in materialized["tracks"]] == ["v2"]
    assert materialized["clips"] == []


def test_segment_request_stamps_astrid_layer_metadata_merged(
    tmp_path: Path,
) -> None:
    """The materialized timeline's metadata gains astrid_layer (alpha = z > 0)
    merged alongside the timeline's own keys, never clobbering them."""
    timeline_path = _layered_timeline(tmp_path)
    candidate = _candidate(
        tmp_path,
        "fixture.full",
        "renderer",
        capabilities={"supports_full_timeline": True, "supports_windows": False},
    )
    request = replace(_request(tmp_path), timeline_path=str(timeline_path))
    service = _service(tmp_path, FakeTransport())

    adapted, sidecar = service._segment_request(
        request,
        candidate=candidate,
        segment=_layered_segment(z=1, tracks=("v2",)),
        index=0,
        workspace=tmp_path,
    )
    materialized = json.loads(
        (tmp_path / "segment-inputs" / "0000-timeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert sidecar["materialized_timeline"]
    assert adapted.window is None
    assert materialized["metadata"]["astrid_layer"] == {"z": 1, "alpha": True}
    # Existing keys survive the merge; the stamp is additive.
    assert materialized["metadata"]["project"] == "layer-slice"
    assert materialized["metadata"]["custom"] == {"keep": 1}
    assert materialized["metadata"]["source_window_start_seconds"] == 0.0
    assert materialized["metadata"]["source_window_end_seconds"] == 1.0
    assert [track["id"] for track in materialized["tracks"]] == ["v2"]
    assert [clip["id"] for clip in materialized["clips"]] == ["c2_0_10"]


def test_segment_request_z0_stamps_alpha_false(tmp_path: Path) -> None:
    """The bottom layer (z=0) is opaque: alpha must be False, not True."""
    timeline_path = _layered_timeline(tmp_path)
    candidate = _candidate(
        tmp_path,
        "fixture.full",
        "renderer",
        capabilities={"supports_full_timeline": True, "supports_windows": False},
    )
    request = replace(_request(tmp_path), timeline_path=str(timeline_path))
    service = _service(tmp_path, FakeTransport())

    service._segment_request(
        request,
        candidate=candidate,
        segment=_layered_segment(z=0, tracks=("v1",)),
        index=1,
        workspace=tmp_path,
    )
    materialized = json.loads(
        (tmp_path / "segment-inputs" / "0001-timeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert materialized["metadata"]["astrid_layer"] == {"z": 0, "alpha": False}
    assert [track["id"] for track in materialized["tracks"]] == ["v1"]


class _TimelineCaptureTransport(FakeTransport):
    """Records the timeline JSON a full-timeline renderer actually receives."""

    def __init__(self) -> None:
        super().__init__()
        self.received_timelines: list[dict[str, Any]] = []

    def run(
        self,
        verb: str,
        command: Any,
        *,
        backend: str,
        request_path: Path,
        result_path: Path,
        cwd: Path,
        **kwargs: Any,
    ) -> Any:
        if verb == "render":
            payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
            timeline_path = payload.get("timeline_path")
            if timeline_path:
                self.received_timelines.append(
                    json.loads(Path(timeline_path).read_text(encoding="utf-8"))
                )
        return super().run(
            verb,
            command,
            backend=backend,
            request_path=request_path,
            result_path=result_path,
            cwd=cwd,
            **kwargs,
        )


@pytest.mark.skip(reason="retired built-in planner")
def test_layer_plan_end_to_end_materializes_track_slice_and_stamp(
    tmp_path: Path,
) -> None:
    """Full service path: a planned layered segment rendered by a
    supports_windows: false renderer receives a materialized timeline with
    ONLY its layer's track/clips and the astrid_layer stamp."""
    timeline_path = _layered_timeline(tmp_path)
    transport = _TimelineCaptureTransport()
    transport.plan = _layered_plan(z=1, tracks=("v2",))
    renderers = RendererRegistry(
        [
            _candidate(
                tmp_path,
                "fixture.full",
                "renderer",
                capabilities={
                    "supports_full_timeline": True,
                    "supports_windows": False,
                },
            )
        ]
    )
    planners = PlannerRegistry(
        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
    )
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
    )
    service = RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )
    output = tmp_path / "layer-slice.mp4"
    request = replace(_request(tmp_path), timeline_path=str(timeline_path))

    service.render_request(request, selector="hybrid", out_path=output)

    assert len(transport.received_timelines) == 1
    materialized = transport.received_timelines[0]
    assert [track["id"] for track in materialized["tracks"]] == ["v2"]
    assert [clip["id"] for clip in materialized["clips"]] == ["c2_0_10"]
    assert materialized["metadata"]["astrid_layer"] == {"z": 1, "alpha": True}
    assert materialized["metadata"]["project"] == "layer-slice"


def test_direct_render_with_pinned_finalizer_records_both_fragments(
    tmp_path: Path,
) -> None:
    """An embedding host pinning `finalizer_id` on a direct render gets the
    renderer artifact lineage AND the executed finalizer fragment."""
    transport = FakeTransport()
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("rendering.remotion",),
        planner_ids=(),
        finalizer_id="rendering.ffmpeg-finalizer",
    )
    output = tmp_path / "direct-finalize.mp4"

    service.render_request(
        replace(_request(tmp_path), backend_config={}),
        selector="rendering.remotion",
        out_path=output,
    )

    payload = _sidecar(output)
    fragments = payload["backend_fragments"]
    assert (
        fragments["rendering.remotion"]["fixture_backend"] == "rendering.remotion"
    )
    assert (
        fragments["rendering.ffmpeg-finalizer"]["fixture_backend"]
        == "rendering.ffmpeg-finalizer"
    )
    assert len(payload["artifact_profiles"]) == 1
    assert payload["finalizer"]["id"] == "rendering.ffmpeg-finalizer"
