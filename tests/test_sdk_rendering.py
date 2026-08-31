"""T6.2 — public rendering SDK surface.

Locks the three public entrypoints in :mod:`astrid.sdk.rendering`:

* ``renderer_main`` round-trips the committed raw-command fixture request and
  writes the SAME result JSON as the raw backend (wire parity, exact field
  equality — no SDK-only fields);
* ``render`` / ``support`` produce valid outputs through a
  FakeTransport-backed :class:`RenderService`;
* importing ``astrid.sdk.rendering`` never imports the rendering service,
  transport, registries, artifacts, or pack backends eagerly.

Run: ``pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py``
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest import mock

from astrid.core.pack import discover_packs as _discover_packs
from astrid.core.rendering import registry as rendering_registry_module
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    FinalizerManifest,
    PlannerManifest,
    RendererManifest,
    RenderProfile,
    RenderRequest,
    RenderResult,
    SupportReport,
    VideoArtifact,
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
from astrid.sdk import rendering as sdk_rendering

ROOT = Path(__file__).resolve().parents[1]
RAW_PACK = ROOT / "tests" / "fixtures" / "renderer_packs" / "raw_command"
REQUESTS_DIR = RAW_PACK / "requests"
BACKEND_ID = "raw_command.renderer"

RENDER_REQUEST_WIRE_FIELDS = frozenset(
    {
        "schema_version",
        "timeline_path",
        "assets_registry_path",
        "output_name",
        "window",
        "audio",
        "profile",
        "backend_config",
        "metadata",
    }
)


# ---------------------------------------------------------------------------
# Raw-command fixture registries (mirrors test_raw_command_fixture.py)
# ---------------------------------------------------------------------------


def _scanner(source_root: Path):
    def scan(root: str | Path | None = None):
        return _discover_packs(source_root if root is None else root)

    return scan


def _registries(tmp_path: Path):
    """Load registries that discover ONLY a copied raw_command fixture pack."""
    extra_root = tmp_path / "extra-packs"
    extra_root.mkdir()
    shutil.copytree(RAW_PACK, extra_root / "raw_command")
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    with (
        mock.patch.object(
            rendering_registry_module,
            "discover_packs",
            side_effect=_scanner(empty_source),
        ),
        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
    ):
        return load_default_registries(
            tmp_path / "project",
            extra_pack_roots=(str(extra_root),),
        )


def _stage_request(workspace: Path, request_name: str) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    request = json.loads((REQUESTS_DIR / request_name).read_text(encoding="utf-8"))
    request_path = workspace / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    timeline = REQUESTS_DIR / "timeline.json"
    if timeline.is_file():
        shutil.copyfile(timeline, workspace / "timeline.json")
    return request_path


def _run_raw_backend(verb: str, request_path: Path, result_path: Path) -> None:
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
        cwd=RAW_PACK,
        check=True,
        capture_output=True,
        text=True,
    )


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"expected a JSON object: {path}"
    return payload


# ---------------------------------------------------------------------------
# FakeTransport-backed service (mirrors test_service.py)
# ---------------------------------------------------------------------------


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _profile() -> RenderProfile:
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
    )


def _candidate(root: Path, capability_id: str, kind: str) -> RenderingCandidate[Any]:
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
            operations=("render", "support"),
            capabilities={"supports_windows": True},
        )
    elif kind == "planner":
        manifest = PlannerManifest(
            **common,
            operations=("plan", "support"),
            capabilities={"supports_fallback": True},
        )
    else:
        manifest = FinalizerManifest(
            **common,
            operations=("finalize", "support"),
            capabilities={"preserves_attachments": True},
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
        priority_index=0,
        eligibility=ExecutionEligibility(
            eligible=True,
            reason="fixture trust",
            trust_method="test",
        ),
    )


class FakeTransport:
    """Deterministic in-process stand-in for the command transport."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.payloads: list[tuple[str, str, dict[str, Any]]] = []
        self.support_reports: dict[str, SupportReport] = {}

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
            return self.support_reports.get(backend) or SupportReport(
                schema_version=SCHEMA_VERSION,
                supported=True,
                reasons=[],
                features={"fixture": True},
                alternatives=[],
                backend=backend,
                backend_version="1.0.0",
            )
        if verb == "render":
            output = workspace / "outputs" / payload["output_name"]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fixture-video")
            window = payload.get("window")
            frames = (
                int(window["end_frame"] - window["start_frame"])
                if window is not None
                else 10
            )
            ownership = AudioOwnership(payload.get("audio") or "none")
            profile = (
                _profile()
                if payload.get("profile") is None
                else RenderProfile.from_dict(payload["profile"])
            )
            video = VideoArtifact.from_file(
                path=output,
                workspace_root=workspace,
                profile=profile,
                duration_frames=frames,
                audio=ownership,
            )
            return RenderResult(
                schema_version=SCHEMA_VERSION,
                video=video,
                audio_ownership=ownership,
                backend_fragments={backend: {"fixture": True}},
            )
        raise AssertionError(f"unexpected verb {verb!r}")


def _service(tmp_path: Path, transport: FakeTransport) -> RenderService:
    renderers = RendererRegistry(
        [_candidate(tmp_path, "fixture.renderer", "renderer")]
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
        publisher=publish_render_result,
    )


# ---------------------------------------------------------------------------
# renderer_main — raw fixture round-trip and wire parity
# ---------------------------------------------------------------------------


def test_renderer_main_render_round_trips_raw_fixture_request(tmp_path: Path) -> None:
    registries = _registries(tmp_path)
    workspace = tmp_path / "workspace"
    request_path = _stage_request(workspace, "render.json")
    sdk_result = workspace / "sdk-result.json"
    raw_result = workspace / "raw-result.json"

    exit_code = sdk_rendering.renderer_main(
        ["render", "--request", str(request_path), "--result", str(sdk_result)],
        registries=registries,
    )

    assert exit_code == 0
    assert sdk_result.is_file()
    _run_raw_backend("render", request_path, raw_result)

    sdk_payload = _json(sdk_result)
    raw_payload = _json(raw_result)
    # Wire parity: the SDK writes the same result JSON as the raw backend,
    # field for field, with no SDK-only fields.
    assert sdk_payload == raw_payload
    assert set(sdk_payload) == {
        "schema_version",
        "video",
        "backend_fragments",
        "audio_ownership",
        "normalization",
        "logs",
        "metadata",
    }
    assert sdk_payload["schema_version"] == SCHEMA_VERSION
    assert sdk_payload["backend_fragments"][BACKEND_ID] == {
        "renderer": "raw_command",
        "media": "generated",
        "audio_mode": "rendered",
        "deterministic": True,
    }
    video = workspace / sdk_payload["video"]["path"]
    assert video.is_file()
    assert hashlib.sha256(video.read_bytes()).hexdigest() == sdk_payload["video"]["sha256"]


def test_renderer_main_support_round_trips_raw_fixture_request(tmp_path: Path) -> None:
    registries = _registries(tmp_path)
    workspace = tmp_path / "workspace"
    request_path = _stage_request(workspace, "support.json")
    sdk_result = workspace / "sdk-result.json"
    raw_result = workspace / "raw-result.json"

    exit_code = sdk_rendering.renderer_main(
        ["support", "--request", str(request_path), "--result", str(sdk_result)],
        registries=registries,
    )

    assert exit_code == 0
    assert sdk_result.is_file()
    _run_raw_backend("support", request_path, raw_result)

    sdk_payload = _json(sdk_result)
    raw_payload = _json(raw_result)
    assert sdk_payload == raw_payload
    assert set(sdk_payload) == {
        "schema_version",
        "supported",
        "reasons",
        "features",
        "alternatives",
        "backend",
        "backend_version",
    }
    assert sdk_payload["supported"] is True
    assert sdk_payload["backend"] == BACKEND_ID
    assert sdk_payload["backend_version"] == "1.0.0"


def test_renderer_main_writes_frozen_protocol_error_for_malformed_request(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    request_path = workspace / "request.json"
    # Missing required timeline_path field.
    request_path.write_text(
        json.dumps({"schema_version": 1, "output_name": "video.mp4"}),
        encoding="utf-8",
    )
    result_path = workspace / "result.json"

    exit_code = sdk_rendering.renderer_main(
        ["render", "--request", str(request_path), "--result", str(result_path)]
    )

    assert exit_code == 0
    payload = _json(result_path)
    assert set(payload) == {
        "schema_version",
        "kind",
        "backend",
        "message",
        "recovery_command",
        "details",
    }
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["kind"] == "protocol"


# ---------------------------------------------------------------------------
# render — public convenience through a FakeTransport-backed service
# ---------------------------------------------------------------------------


def test_render_returns_published_path_through_fake_transport(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    timeline = tmp_path / "timeline.json"
    assets = tmp_path / "assets.json"
    timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")
    assets.write_text('{"assets": {}}', encoding="utf-8")
    out_path = tmp_path / "published" / "video.mp4"

    published = sdk_rendering.render(
        timeline,
        assets_registry_path=assets,
        output_name="video.mp4",
        out_path=out_path,
        selector="fixture.renderer",
        service=service,
    )

    assert published == out_path
    assert out_path.is_file()
    assert out_path.stat().st_size > 0
    assert Path(f"{out_path}.provenance.json").is_file()
    assert ("support", "fixture.renderer") in transport.calls
    assert ("render", "fixture.renderer") in transport.calls


def test_render_builds_request_with_exact_frozen_wire_fields(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    timeline = tmp_path / "timeline.json"
    assets = tmp_path / "assets.json"
    timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")
    assets.write_text('{"assets": {}}', encoding="utf-8")
    out_path = tmp_path / "video.mp4"

    sdk_rendering.render(
        timeline,
        assets_registry_path=assets,
        output_name="video.mp4",
        out_path=out_path,
        selector="fixture.renderer",
        backend_config={"fixture.renderer": {"mode": "solid"}},
        metadata={"fixture": "sdk"},
        service=service,
    )

    render_payloads = [
        payload for verb, _backend, payload in transport.payloads if verb == "render"
    ]
    assert render_payloads
    payload = render_payloads[0]
    # The SDK-built request serializes to EXACTLY the frozen wire field set:
    # no SDK-only fields, no omissions.
    assert set(payload) == RENDER_REQUEST_WIRE_FIELDS
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["timeline_path"] == str(timeline.resolve())
    assert payload["assets_registry_path"] == str(assets.resolve())
    assert payload["output_name"] == "video.mp4"
    assert payload["window"] is None
    assert payload["audio"] is None
    assert payload["profile"] is None
    assert payload["backend_config"] == {"fixture.renderer": {"mode": "solid"}}
    assert payload["metadata"] == {"fixture": "sdk"}


# ---------------------------------------------------------------------------
# support — public convenience through a FakeTransport-backed service
# ---------------------------------------------------------------------------


def test_support_returns_report_through_fake_transport(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.support_reports["fixture.renderer"] = SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=False,
        reasons=["fixture timeline is unsupported"],
        features={"media": False, "audio_mode": "none"},
        alternatives=[],
        backend="fixture.renderer",
        backend_version="1.0.0",
    )
    service = _service(tmp_path, transport)
    request = RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(tmp_path / "timeline.json"),
        output_name="video.mp4",
        audio=AudioOwnership.NONE,
    )

    report = sdk_rendering.support(
        "fixture.renderer",
        request=request,
        service=service,
    )

    assert isinstance(report, SupportReport)
    assert report.supported is False
    assert report.reasons == ["fixture timeline is unsupported"]
    assert report.features == {"media": False, "audio_mode": "none"}
    assert report.backend == "fixture.renderer"
    assert report.backend_version == "1.0.0"
    assert ("support", "fixture.renderer") in transport.calls


def test_support_accepts_friendly_args_and_wire_mapping(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    timeline = tmp_path / "timeline.json"
    timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")

    friendly = sdk_rendering.support(
        "fixture.renderer",
        timeline_path=timeline,
        output_name="video.mp4",
        audio="none",
        service=service,
    )
    assert friendly.supported is True
    assert friendly.backend == "fixture.renderer"

    mapping_report = sdk_rendering.support(
        "fixture.renderer",
        request={
            "schema_version": SCHEMA_VERSION,
            "timeline_path": str(timeline),
            "output_name": "video.mp4",
            "audio": "none",
        },
        service=service,
    )
    assert mapping_report.backend == "fixture.renderer"
    assert mapping_report.supported is True


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------


def test_importing_sdk_rendering_does_not_import_heavy_modules() -> None:
    script = """
import json
import sys

import astrid.sdk.rendering

heavy = (
    "astrid.core.rendering.service",
    "astrid.core.rendering.transport",
    "astrid.core.rendering.registry",
    "astrid.core.rendering.artifacts",
    "astrid.core.rendering.publication",
    "astrid.core.rendering.provenance",
    "astrid.packs.rendering.run",
)
print(json.dumps({name: (name in sys.modules) for name in heavy}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = json.loads(completed.stdout)
    assert loaded == {name: False for name in loaded}
