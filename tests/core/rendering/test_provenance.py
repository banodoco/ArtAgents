from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file
from astrid.core.pack.alias_resolver import AliasResolver
from astrid.core.rendering import publication
from astrid.core.rendering.contracts import RenderPlan
from astrid.core.rendering.provenance import (
    assemble_provenance_v2,
    validate_backend_fragments,
)
from astrid.core.rendering.publication import (
    is_render_result_committed,
    publish_render_result,
    read_committed_provenance,
)
from astrid.core.rendering.registry import (
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
)
from astrid.core.rendering.service import RenderService
from tests.core.rendering.test_service import (
    FakeTransport,
    _candidate,
    _finalizer_resolution,
    _mixed_plan,
    _mixed_service,
    _plan,
    _request,
    _service,
)


def _sidecar(output: Path) -> Path:
    return Path(f"{output}.provenance.json")


def _read_sidecar(output: Path) -> dict[str, Any]:
    return json.loads(_sidecar(output).read_text(encoding="utf-8"))


def _lineage_service(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    provenance_builder: Any,
) -> RenderService:
    aliases: dict[str, AliasResolver] = {}
    for kind, requested, canonical in (
        ("planner", "rendering.legacy_hybrid", "lineage.planner"),
        ("renderer", "lineage.renderer-alias", "lineage.renderer"),
        ("finalizer", "lineage.finalizer-alias", "lineage.finalizer"),
    ):
        resolver = AliasResolver()
        resolver.register_alias(requested, canonical)
        aliases[kind] = resolver

    renderers = RendererRegistry(
        [_candidate(tmp_path, "lineage.renderer-v2", "renderer")],
        alias_resolver=aliases["renderer"],
    )
    planners = PlannerRegistry(
        [_candidate(tmp_path, "lineage.planner-v2", "planner")],
        alias_resolver=aliases["planner"],
    )
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "lineage.finalizer-v2", "finalizer")],
        alias_resolver=aliases["finalizer"],
    )
    return RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=lambda result, **_kwargs: result,
        provenance_builder=provenance_builder,
    )


@pytest.mark.skip(reason="retired built-in planner")
def test_service_plan_round_trips_complete_routing_lineage(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.plan = replace(
        _plan("lineage.renderer-alias", segment_frames=(5, 5)),
        finalizer=_finalizer_resolution("lineage.finalizer-alias"),
    )
    captured: dict[str, RenderPlan] = {}

    def capture_provenance(**kwargs: Any) -> dict[str, Any]:
        plan = kwargs["plan"]
        captured["plan"] = RenderPlan.from_dict(plan.to_dict())
        return assemble_provenance_v2(**kwargs)

    service = _lineage_service(
        tmp_path,
        transport,
        provenance_builder=capture_provenance,
    )
    request = _request(tmp_path)
    output = tmp_path / "lineage.mp4"

    service.render_request(request, selector="hybrid", out_path=output)

    plan = captured["plan"]
    payload = _read_sidecar(output)
    assert payload["request_digest"] == plan.request_digest
    assert payload["requested_policy"] == "hybrid"
    assert payload["planner"] == plan.planner.to_dict()
    assert payload["segments_v2"] == [
        segment.to_dict() for segment in plan.segments
    ]
    assert payload["finalizer"] == plan.finalizer.to_dict()

    planner = payload["planner"]
    assert planner["alias_chain"] == [
        "rendering.legacy_hybrid",
        "lineage.planner",
    ]
    assert planner["override"] == {
        "from": "lineage.planner",
        "to": "lineage.planner-v2",
    }
    assert planner["manifest_digest"] == hashlib.sha256(
        b"lineage.planner-v2"
    ).hexdigest()
    assert planner["trust_eligibility"]["eligible"] is True
    assert planner["support_decision"]["backend"] == "lineage.planner-v2"

    for segment in payload["segments_v2"]:
        renderer = segment["renderer"]
        assert renderer["alias_chain"] == [
            "lineage.renderer-alias",
            "lineage.renderer",
        ]
        assert renderer["override"] == {
            "from": "lineage.renderer",
            "to": "lineage.renderer-v2",
        }
        assert renderer["trust_eligibility"]["eligible"] is True
        assert renderer["support_decision"]["backend"] == "lineage.renderer-v2"
        assert segment["input_hashes"]["timeline"] == sha256_file(
            Path(request.timeline_path)
        )
        assert segment["input_hashes"]["assets_registry"] == sha256_file(
            Path(request.assets_registry_path or "")
        )

    finalizer = payload["finalizer"]
    assert finalizer["alias_chain"] == [
        "lineage.finalizer-alias",
        "lineage.finalizer",
    ]
    assert finalizer["override"] == {
        "from": "lineage.finalizer",
        "to": "lineage.finalizer-v2",
    }
    assert finalizer["trust_eligibility"]["eligible"] is True
    assert finalizer["support_decision"]["backend"] == "lineage.finalizer-v2"

    expected_policy = {
        "planner": "lineage.planner-v2",
        "renderers": ["lineage.renderer-v2"],
        "finalizer": "lineage.finalizer-v2",
    }
    assert payload["resolved_policy"] == expected_policy
    assert payload["routing"] == {
        "requested_engine": "hybrid",
        "requested_policy": "hybrid",
        "resolved_policy": expected_policy,
        "resolved_backend": "lineage.renderer-v2",
        "resolved_backends": ["lineage.renderer-v2"],
        "auto_route": False,
        "auto_route_reason": None,
        "segment_reasons": plan.reasons,
    }
    assert len(payload["artifact_profiles"]) == 2
    for artifact in payload["artifact_profiles"]:
        assert artifact["sha256"] == hashlib.sha256(
            b"render:lineage.renderer-v2:5"
        ).hexdigest()
        assert artifact["attachments"] == {}
    assert payload["audio_ownership"] == "none"
    assert payload["normalization"] == []
    assert payload["attachments"] == {}
    assert set(payload["backend_fragments"]) == {
        "lineage.renderer-v2",
        "lineage.finalizer-v2",
    }


@pytest.mark.skip(reason="retired shorthand and fallback route")
def test_legacy_remotion_auto_route_reason_is_recorded(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "legacy-remotion.mp4"

    with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
        service.render_request(
            _request(tmp_path),
            selector="remotion",
            out_path=output,
        )

    payload = _read_sidecar(output)
    routing = payload["routing"]
    assert routing["requested_engine"] == "remotion"
    assert routing["resolved_backend"] == "rendering.ffmpeg"
    assert routing["auto_route"] is True
    assert routing["auto_route_reason"] == (
        "legacy selector 'remotion' auto-routed the supported request to "
        "rendering.ffmpeg"
    )


def test_every_v1_top_level_projection_is_preserved(tmp_path: Path) -> None:
    compatibility = {
        "project_dir": "/workspace/remotion",
        "composition_id": "TimelineComposition",
        "active_pack_order": [{"id": "builtin", "version": "1.0.0"}],
        "active_theme": {"id": "fixture.theme"},
        "registry_hash": "1" * 64,
        "registry_state": {"effects": ["fixture.effect"]},
        "resolved_effect_ids": ["fixture.effect"],
        "resolved_effects": [{"id": "fixture.effect"}],
        "source_pack_ids": ["fixture"],
        "element_roots": ["astrid/packs/fixture/elements"],
        "staged_asset_ids": ["fixture.badge"],
        "staged_asset_root": "remotion/public/astrid-effects/render",
        "segment_provenance": [
            {"engine": "legacy", "from": 0.0, "to": 1.0}
        ],
        "ffmpeg_specialization": "fixture.specialization",
        "audio_reactive_colour": {"effect_id": "fixture.colour"},
    }
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    request = _request(tmp_path)
    output = tmp_path / "v1-projections.mp4"

    service.render_request(
        request,
        selector="rendering.ffmpeg",
        out_path=output,
        v1_compatibility=compatibility,
    )

    payload = _read_sidecar(output)
    expected_keys = {
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
        "segments",
        "segment_provenance",
        "ffmpeg_specialization",
        "audio_reactive_colour",
    }
    assert expected_keys <= set(payload)
    assert payload["engine"] == "rendering.ffmpeg"
    assert payload["output"] == str(output.resolve())
    assert payload["timeline"] == request.timeline_path
    assert payload["assets_registry"] == request.assets_registry_path
    assert payload["segments"] == [
        {"engine": "ffmpeg", "from": 0.0, "to": 1.0}
    ]
    for key, value in compatibility.items():
        assert payload[key] == value


@pytest.mark.parametrize("core_key", ["routing", "resolved_policy", "engine"])
def test_backend_fragment_core_key_collision_is_rejected(core_key: str) -> None:
    with pytest.raises(ValueError, match="core-owned keys"):
        validate_backend_fragments(
            {"lineage.renderer": {core_key: "backend-owned-spoof"}}
        )


def test_one_sidecar_is_committed_per_success(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "one-sidecar.mp4"

    service.render_request(
        _request(tmp_path), selector="rendering.ffmpeg", out_path=output
    )

    sidecars = list(tmp_path.rglob("*.provenance.json"))
    assert sidecars == [_sidecar(output)]
    payload = read_committed_provenance(output, sidecar_path=sidecars[0])
    assert payload is not None
    assert payload["sha256"] == sha256_file(output)


def test_previous_output_cleanup_skips_a_live_locked_render(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    request = _request(tmp_path)
    previous = tmp_path / "previous" / "video.mp4"
    previous.parent.mkdir()
    previous.write_bytes(b"still-live")
    previous_sidecar = _sidecar(previous)
    write_json_atomic(
        previous_sidecar,
        {
            "output": str(previous.resolve()),
            "timeline": request.timeline_path,
            "sha256": sha256_file(previous),
        },
    )
    lock = publication._lock_for(previous)
    lock.acquire(timeout=0)
    output = tmp_path / "current" / "video.mp4"
    try:
        service.render_request(
            request,
            selector="rendering.ffmpeg",
            out_path=output,
            previous_outputs=[previous],
        )
    finally:
        lock.release()

    assert previous.read_bytes() == b"still-live"
    assert read_committed_provenance(
        previous, sidecar_path=previous_sidecar
    ) is not None
    assert read_committed_provenance(
        output, sidecar_path=_sidecar(output)
    ) is not None


# ---------------------------------------------------------------------------
# T4.5 — provenance / crash-recovery matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("selector", "hybrid_plan", "expected_engine", "expected_backend", "auto_route"),
    [
        (
            "rendering.remotion",
            False,
            "rendering.remotion",
            "rendering.remotion",
            False,
        ),
        (
            "rendering.ffmpeg",
            False,
            "rendering.ffmpeg",
            "rendering.ffmpeg",
            False,
        ),
        ("ffmpeg", False, "ffmpeg", "rendering.ffmpeg", False),
        ("remotion", False, "remotion", "rendering.ffmpeg", True),
        ("hybrid", True, "hybrid", "fixture.window", False),
    ],
    ids=[
        "qualified-remotion",
        "qualified-ffmpeg",
        "legacy-ffmpeg",
        "legacy-remotion",
        "hybrid",
    ],
)
@pytest.mark.skip(reason="retired shorthand and planner selectors")
def test_routing_fields_matrix_for_every_selector(
    tmp_path: Path,
    selector: str,
    hybrid_plan: bool,
    expected_engine: str,
    expected_backend: str,
    auto_route: bool,
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

    if auto_route:
        with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
            service.render_request(
                _request(tmp_path), selector=selector, out_path=output
            )
    else:
        service.render_request(
            _request(tmp_path), selector=selector, out_path=output
        )

    payload = _read_sidecar(output)
    routing = payload["routing"]
    assert routing["requested_engine"] == expected_engine
    assert routing["resolved_backend"] == expected_backend
    assert routing["resolved_backends"] == [expected_backend]
    assert routing["auto_route"] is auto_route
    resolved_policy = routing["resolved_policy"]
    assert resolved_policy["renderers"] == [expected_backend]
    if hybrid_plan:
        assert resolved_policy["planner"] == "rendering.legacy_hybrid"
        assert resolved_policy["finalizer"] == "rendering.ffmpeg-finalizer"
    assert payload["requested_policy"] == expected_engine


@pytest.mark.skip(reason="retired built-in planner")
def test_raw_mixed_plan_segment_provenance_is_aligned(tmp_path: Path) -> None:
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
    output = tmp_path / "mixed-provenance.mp4"

    service.render_request(request, selector="hybrid", out_path=output)

    payload = _read_sidecar(output)
    segments = payload["segments_v2"]
    assert [segment["renderer"]["id"] for segment in segments] == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    assert all(
        "timeline" in segment["input_hashes"] for segment in segments
    )
    assert all(
        "assets_registry" in segment["input_hashes"] for segment in segments
    )
    assert payload["finalizer"]["id"] == "rendering.ffmpeg-finalizer"
    routing = payload["routing"]
    assert routing["requested_engine"] == "hybrid"
    assert routing["resolved_backend"] is None  # multi-segment: no single winner
    assert routing["resolved_backends"] == [
        "raw_command.renderer",
        "rendering.remotion",
    ]
    assert set(payload["backend_fragments"]) == {
        "raw_command.renderer",
        "rendering.remotion",
        "rendering.ffmpeg-finalizer",
    }
    assert payload["segments"] == [
        {"engine": "renderer", "from": 0.0, "to": 1.75},
        {"engine": "remotion", "from": 1.75, "to": 3.25},
        {"engine": "renderer", "from": 3.25, "to": 6.0},
    ]


def test_attachments_are_recorded_in_committed_provenance(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.render_attachments["rendering.ffmpeg"] = {
        "badge.png": b"badge-bytes"
    }
    service = _service(tmp_path, transport)
    output = tmp_path / "attachment-provenance.mp4"

    service.render_request(
        _request(tmp_path), selector="rendering.ffmpeg", out_path=output
    )

    payload = _read_sidecar(output)
    attachment = payload["attachments"]["badge.png"]
    assert attachment["sha256"] == hashlib.sha256(b"badge-bytes").hexdigest()
    assert attachment["kind"] == "fixture"
    committed = read_committed_provenance(output, sidecar_path=_sidecar(output))
    assert committed is not None
    assert committed["attachments"] == payload["attachments"]
    assert committed["artifact_profiles"] == payload["artifact_profiles"]


@pytest.mark.parametrize(
    "scenario",
    [
        "video-only",
        "sidecar-only",
        "hash-mismatch",
        "wrong-output",
        "empty-video",
        "malformed-sidecar",
    ],
)
def test_incomplete_pair_never_read_as_committed(
    tmp_path: Path, scenario: str
) -> None:
    video = tmp_path / "video.mp4"
    sidecar = _sidecar(video)
    valid_payload = {
        "output": str(video.resolve()),
        "timeline": str(tmp_path / "timeline.json"),
        "sha256": hashlib.sha256(b"media-bytes").hexdigest(),
        "engine": "ffmpeg",
    }

    if scenario == "video-only":
        video.write_bytes(b"media-bytes")
    elif scenario == "sidecar-only":
        write_json_atomic(sidecar, valid_payload)
    elif scenario == "hash-mismatch":
        video.write_bytes(b"media-bytes")
        write_json_atomic(sidecar, dict(valid_payload, sha256="0" * 64))
    elif scenario == "wrong-output":
        video.write_bytes(b"media-bytes")
        write_json_atomic(
            sidecar,
            dict(valid_payload, output=str((tmp_path / "elsewhere.mp4").resolve())),
        )
    elif scenario == "empty-video":
        video.write_bytes(b"")
        write_json_atomic(sidecar, valid_payload)
    elif scenario == "malformed-sidecar":
        video.write_bytes(b"media-bytes")
        sidecar.write_text("{not json", encoding="utf-8")

    assert read_committed_provenance(video, sidecar_path=sidecar) is None
    assert is_render_result_committed(video, sidecar_path=sidecar) is False


def test_valid_pair_is_read_as_committed(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"media-bytes")
    payload = {
        "output": str(video.resolve()),
        "timeline": str(tmp_path / "timeline.json"),
        "sha256": hashlib.sha256(b"media-bytes").hexdigest(),
        "engine": "ffmpeg",
    }
    write_json_atomic(_sidecar(video), payload)

    committed = read_committed_provenance(video, sidecar_path=_sidecar(video))
    assert committed is not None
    assert committed["sha256"] == payload["sha256"]
    assert is_render_result_committed(video, sidecar_path=_sidecar(video)) is True


def test_orphaned_video_after_publish_is_never_committed(tmp_path: Path) -> None:
    staged = tmp_path / "stage" / "video.mp4"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(b"published-media")
    output = tmp_path / "out" / "video.mp4"
    provenance = {
        "timeline": str(tmp_path / "timeline.json"),
        "engine": "ffmpeg",
        "requested_policy": "ffmpeg",
    }

    published = publish_render_result(
        staged,
        provenance,
        out_path=output,
        sidecar_path=_sidecar(output),
    )
    assert published == output
    assert read_committed_provenance(output, sidecar_path=_sidecar(output)) is not None

    # A crash between the video move and the atomic sidecar write leaves an
    # orphan video: visible for recovery, never treated as committed.
    _sidecar(output).unlink()
    assert read_committed_provenance(output, sidecar_path=_sidecar(output)) is None
    assert is_render_result_committed(output, sidecar_path=_sidecar(output)) is False
    assert output.read_bytes() == b"published-media"
