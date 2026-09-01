"""rendering.threejs backend — thin Three.js timeline renderer tests.

Locks the batch-3 epic promise: ``rendering.threejs`` is its OWN renderer
(identity/provenance never claims ``rendering.remotion``) that renders
complete Astrid timelines through the ``ThreeTimelineComposition`` via the
shared Remotion execution helper + lock.  The test exercises:

* static manifest discovery + registry inspection;
* honest support (text-only, background-only/empty accepted; media/hold/
  effect-layer/unknown clips, effects, transitions, animation, opacity != 1,
  unsupported text fields/params, audio tracks/audible clips and
  passthrough/none ownership rejected with stable clip-specific reasons);
* window == None enforced on support and render;
* own-namespace config only (unknown keys rejected, other backends' config
  ignored, v1 render accepts no own-namespace config);
* protocol failure results are valid structured errors;
* a real render through the public service (Node + ffprobe + remotion
  project with three/@remotion/three/@react-three/fiber required).

The real-render cases SKIP only when the environment is genuinely missing;
a render failure is never turned into a skip.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    FrameWindow,
    RendererManifest,
    RenderRequest,
)
from astrid.core.rendering.errors import RendererUnsupportedError
from astrid.core.rendering.registry import load_default_registries
from astrid.packs.rendering.backends.remotion import lock as remotion_lock
from astrid.packs.rendering.backends.remotion import run as remotion_backend
from astrid.packs.rendering.backends.threejs import run as threejs
from astrid.packs.rendering.executors.render.run import render
from astrid.sdk.rendering import support
from tests.packs.rendering._helpers import _execution_env, _frame_md5, _probe

ROOT = Path(__file__).resolve().parents[3]
RENDERING_PACK = ROOT / "astrid" / "packs" / "rendering"
REMOTION_PROJECT = ROOT / "remotion"
MANIFEST = (
    RENDERING_PACK / "backends" / "threejs" / "renderer.yaml"
)
THREEJS_ID = "rendering.threejs"

CANVAS = {"width": 320, "height": 180, "fps": 24}


def _missing_environment() -> list[str]:
    missing = [
        f"{binary} executable"
        for binary in ("node", "npx", "ffprobe")
        if shutil.which(binary) is None
    ]
    node_modules = REMOTION_PROJECT / "node_modules"
    if not node_modules.is_dir():
        missing.append("remotion/node_modules")
    for package in ("three", "@remotion/three", "@react-three/fiber"):
        if not (node_modules / package).is_dir():
            missing.append(f"remotion/node_modules/{package}")
    # The transport spawns `python3` from PATH; the active interpreter must
    # carry the banodoco timeline schema or timeline serialization is refused.
    try:
        import banodoco_timeline_schema  # noqa: F401
    except ImportError:
        missing.append("banodoco_timeline_schema for the active python3")
    return missing


def _require_threejs_environment() -> None:
    missing = _missing_environment()
    if missing:
        pytest.skip(
            "Three.js backend real render skipped: missing optional "
            "dependencies: " + ", ".join(missing)
        )


@pytest.fixture(autouse=True)
def _threejs_exec_env():
    """Transport-spawned children must resolve the same node and the same
    python3 (with the banodoco timeline schema) as the test process."""
    with _execution_env():
        yield


def _write_timeline(tmp_path: Path, payload: dict) -> Path:
    pytest.importorskip(
        "banodoco_timeline_schema",
        reason="canonical timeline schema is required for timeline renderer tests",
    )
    path = tmp_path / "timeline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _text_timeline(tmp_path: Path) -> Path:
    return _write_timeline(
        tmp_path,
        {
            "theme": "banodoco-default",
            "theme_overrides": {
                "visual": {"canvas": dict(CANVAS), "background": "#1a1a2e"}
            },
            "tracks": [{"id": "v1", "kind": "visual", "label": "Title"}],
            "clips": [
                {
                    "id": "title",
                    "at": 0.0,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 0.5,
                    "text": {"content": "Hello Three.js", "fontSize": 64, "color": "#ffffff"},
                    "params": {"weight": 700},
                }
            ],
        },
    )


def _empty_timeline(tmp_path: Path) -> Path:
    return _write_timeline(
        tmp_path,
        {
            "theme": "banodoco-default",
            "theme_overrides": {
                "visual": {"canvas": dict(CANVAS), "background": "#1a1a2e"}
            },
            "tracks": [{"id": "v1", "kind": "visual", "label": "Empty"}],
            "clips": [],
        },
    )


def _request(timeline_path: Path, output_name: str = "threejs.mp4", **kwargs) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "timeline_path": str(timeline_path),
        "assets_registry_path": None,
        "output_name": output_name,
    }
    payload.update(kwargs)
    return payload


# ---------------------------------------------------------------------------
# Manifest + registry discovery
# ---------------------------------------------------------------------------


def test_threejs_manifest_registers_static_raw_command_backend() -> None:
    manifest = RendererManifest.from_dict(
        yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    )

    assert manifest.id == THREEJS_ID
    assert manifest.protocol_version == 1
    assert manifest.command == ("python3", "backends/threejs/run.py")
    assert manifest.operations == ("support", "render")
    assert manifest.required_permissions == ("project_files", "subprocess")
    assert manifest.required_binaries == ("node", "npx", "ffprobe")
    assert manifest.timeout_seconds == 600
    capabilities = manifest.capabilities
    assert capabilities["clip_types"] == ["text"]
    assert capabilities["track_types"] == ["visual"]
    assert capabilities["supports_full_timeline"] is True
    assert capabilities["supports_windows"] is False
    assert capabilities["output_profiles"] == ["video/mp4"]
    assert capabilities["audio_ownership"] == ["rendered"]
    features = capabilities["features"]
    # Frozen contract: every features value is a bool or string, never a list.
    assert all(isinstance(value, (bool, str)) for value in features.values())
    assert features["webgl"] is True
    assert features["capture_host"] == "remotion"
    assert features["effects"] is False
    assert features["transitions"] is False
    assert (RENDERING_PACK / manifest.command[1]).is_file()


def test_threejs_is_discovered_and_inspected() -> None:
    renderers, _planners, _finalizers = load_default_registries(
    )
    candidates = renderers.candidates(THREEJS_ID)
    assert len(candidates) == 1, [c.to_dict() for c in candidates]
    candidate = candidates[0]
    assert candidate.id == THREEJS_ID
    assert candidate.pack_id == "rendering"
    assert candidate.source_kind == "source"
    assert candidate.manifest.command == ("python3", "backends/threejs/run.py")
    assert candidate.manifest.required_binaries == ("node", "npx", "ffprobe")
    assert candidate.execution_eligible is True
    assert (candidate.pack_root / candidate.manifest.command[1]).is_file()


# ---------------------------------------------------------------------------
# Honest support + identity invariants
# ---------------------------------------------------------------------------


def test_threejs_support_accepts_empty_and_exact_text_fields(tmp_path: Path) -> None:
    empty = _empty_timeline(tmp_path)
    report = support(THREEJS_ID, timeline_path=empty)
    assert report.supported is True, report.reasons
    assert report.reasons == []
    assert report.backend == THREEJS_ID
    assert report.backend_version == threejs.BACKEND_VERSION
    assert report.features["audio_ownership"] == "rendered"
    assert report.features["capture_host"] == "remotion"
    assert report.features["webgl"] is True

    text = _text_timeline(tmp_path)
    report = support(THREEJS_ID, timeline_path=text)
    assert report.supported is True, report.reasons
    assert report.reasons == []


def test_threejs_support_rejects_unsupported_timelines_with_clip_reasons(
    tmp_path: Path,
) -> None:
    def reasons_for(clip: dict, tracks: list[dict] | None = None) -> list[str]:
        payload = {
            "theme": "banodoco-default",
            "theme_overrides": {"visual": {"canvas": dict(CANVAS)}},
            "tracks": tracks or [{"id": "v1", "kind": "visual", "label": "V"}],
            "clips": [clip],
        }
        timeline_path = _write_timeline(tmp_path, payload)
        return support(THREEJS_ID, timeline_path=timeline_path).reasons

    # Unsupported clip types -> stable clip-specific reason.
    for clip_type in ("media", "hold", "effect-layer", "mystery"):
        reasons = reasons_for(
            {"id": "c", "at": 0, "track": "v1", "clipType": clip_type}
        )
        assert any(
            f"clip[0] clipType {clip_type!r} is not supported" in reason
            for reason in reasons
        ), (clip_type, reasons)

    # Effects / transitions / animation / opacity != 1.
    reasons = reasons_for(
        {
            "id": "c",
            "at": 0,
            "track": "v1",
            "clipType": "text",
            "hold": 1,
            "effects": [{}],
            "text": {"content": "x"},
        }
    )
    assert any("clip[0] effects are not supported" in r for r in reasons)
    reasons = reasons_for(
        {
            "id": "c",
            "at": 0,
            "track": "v1",
            "clipType": "text",
            "hold": 1,
            "transition": {"id": "cross-fade", "duration": 0.2},
            "text": {"content": "x"},
        }
    )
    assert any("clip[0] transitions are not supported" in r for r in reasons)
    reasons = reasons_for(
        {
            "id": "c",
            "at": 0,
            "track": "v1",
            "clipType": "text",
            "hold": 1,
            "opacity": 0.5,
            "text": {"content": "x"},
        }
    )
    assert any("clip[0] opacity != 1 is not supported" in r for r in reasons)
    # animation is rejected by the pure eligibility helper (the shared
    # timeline validator rejects the key earlier, so the helper is tested
    # directly on raw serialized data).
    raw_reasons = threejs._support_reasons(
        {
            "theme_overrides": {"visual": {"canvas": dict(CANVAS)}},
            "tracks": [{"id": "v1", "kind": "visual", "label": "V"}],
            "clips": [
                {
                    "id": "c",
                    "at": 0,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 1,
                    "animation": {"id": "fade-up"},
                    "text": {"content": "x"},
                }
            ],
        }
    )
    assert any("clip[0] animation is not supported" in r for r in raw_reasons)

    # Unsupported text fields: the shared timeline schema already refuses
    # unknown `text` keys, so the backend's own text-field check is locked
    # on the pure eligibility helper.
    raw_reasons = threejs._support_reasons(
        {
            "theme_overrides": {"visual": {"canvas": dict(CANVAS)}},
            "tracks": [{"id": "v1", "kind": "visual", "label": "V"}],
            "clips": [
                {
                    "id": "c",
                    "at": 0,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 1,
                    "text": {"content": "x", "fadeIn": 0.3},
                }
            ],
        }
    )
    assert any("clip[0] unsupported text fields" in r for r in raw_reasons)
    reasons = reasons_for(
        {
            "id": "c",
            "at": 0,
            "track": "v1",
            "clipType": "text",
            "hold": 1,
            "text": {"content": "x"},
            "params": {"fadeIn": 0.3},
        }
    )
    assert any("clip[0] unsupported text params" in r for r in reasons)

    # Audio tracks and audible clips.
    reasons = reasons_for(
        {
            "id": "c",
            "at": 0,
            "track": "a1",
            "clipType": "text",
            "hold": 1,
            "text": {"content": "x"},
        },
        tracks=[
            {"id": "v1", "kind": "visual", "label": "V"},
            {"id": "a1", "kind": "audio", "label": "A"},
        ],
    )
    assert any("audio tracks are not supported" in r for r in reasons)
    assert any("clip[0] sits on an audio track" in r for r in reasons)
    reasons = reasons_for(
        {
            "id": "c",
            "at": 0,
            "track": "v1",
            "clipType": "text",
            "hold": 1,
            "volume": 1,
            "text": {"content": "x"},
        }
    )
    assert any("clip[0] carries audio" in r for r in reasons)


def test_threejs_support_rejects_non_rendered_audio_ownership(tmp_path: Path) -> None:
    timeline_path = _text_timeline(tmp_path)
    for ownership in ("passthrough", "none"):
        report = support(
            THREEJS_ID, timeline_path=timeline_path, audio=ownership
        )
        assert report.supported is False
        assert any(
            f"audio={ownership!r} is incompatible" in reason
            for reason in report.reasons
        ), report.reasons


def test_threejs_support_and_render_reject_native_window(tmp_path: Path) -> None:
    timeline_path = _text_timeline(tmp_path)
    window = FrameWindow(start_frame=0, end_frame=30, fps_rational=(24, 1))
    report = support(THREEJS_ID, timeline_path=timeline_path, window=window)
    assert report.supported is False
    assert any("native frame windows" in reason for reason in report.reasons)

    from astrid.core.rendering.contracts import RenderRequest

    request = RenderRequest.from_dict(
        _request(timeline_path, window=window.to_dict())
    ).for_backend(THREEJS_ID)
    with pytest.raises(RendererUnsupportedError):
        threejs._protocol_render(request, workspace=tmp_path)


def test_threejs_identity_invariants_never_claim_remotion(tmp_path: Path) -> None:
    """Every support surface reports rendering.threejs and no surface claims
    rendering.remotion."""
    timeline_path = _text_timeline(tmp_path)
    report = support(THREEJS_ID, timeline_path=timeline_path)
    assert report.supported is True, report.reasons
    serialized = json.dumps(report.to_dict())
    assert THREEJS_ID in serialized
    assert "rendering.remotion" not in serialized
    assert report.backend == THREEJS_ID
    # The transport support decision backend equals the renderer id.
    assert report.to_dict()["backend"] == "rendering.threejs"


def test_threejs_own_namespace_config_is_strict(tmp_path: Path) -> None:
    timeline_path = _text_timeline(tmp_path)

    # Unknown own-namespace key -> explicit rejection reason.
    report = support(
        THREEJS_ID,
        timeline_path=timeline_path,
        backend_config={THREEJS_ID: {"bogus_key": 1}},
    )
    assert report.supported is False
    assert any(
        "unknown rendering.threejs configuration: bogus_key" in reason
        for reason in report.reasons
    ), report.reasons

    # Other backends' config is ignored by the own namespace.
    report = support(
        THREEJS_ID,
        timeline_path=timeline_path,
        backend_config={"rendering.remotion": {"project_dir": "/nope"}},
    )
    assert report.supported is True, report.reasons

    # v1 render rejects any non-empty own-namespace backend_config.
    from astrid.core.rendering.contracts import RenderRequest

    request = RenderRequest.from_dict(
        _request(
            timeline_path,
            backend_config={THREEJS_ID: {"min_free_gb": 0.1}},
        )
    ).for_backend(THREEJS_ID)
    with pytest.raises(RendererUnsupportedError) as excinfo:
        threejs._protocol_render(request, workspace=tmp_path)
    assert "no backend_config" in str(excinfo.value)

    # ...but ignores other backends' config on render too (own namespace
    # empty after projection).
    request = RenderRequest.from_dict(
        _request(
            timeline_path,
            backend_config={"rendering.remotion": {"project_dir": "/nope"}},
        )
    ).for_backend(THREEJS_ID)
    assert request.backend_config == {}


# ---------------------------------------------------------------------------
# Protocol failure results are valid structured errors
# ---------------------------------------------------------------------------


def _run_protocol(verb: str, tmp_path: Path, payload: dict) -> dict:
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    code = threejs.main([verb, "--request", str(request_path), "--result", str(result_path)])
    assert code == 0
    return json.loads(result_path.read_text(encoding="utf-8"))


def test_threejs_protocol_failure_results_are_valid(tmp_path: Path) -> None:
    timeline_path = _text_timeline(tmp_path)

    # Unsupported render (non-empty own-namespace config) -> RendererError.
    result = _run_protocol(
        "render",
        tmp_path,
        _request(
            timeline_path,
            output_name="cfg.mp4",
            backend_config={THREEJS_ID: {"project_dir": str(REMOTION_PROJECT)}},
        ),
    )
    assert result["schema_version"] == 1
    assert result["kind"] == "unsupported"
    assert result["backend"] == THREEJS_ID
    assert isinstance(result["message"], str) and result["message"]

    # Malformed request JSON -> protocol error.
    request_path = tmp_path / "bad.json"
    result_path = tmp_path / "bad-result.json"
    request_path.write_text("{not json", encoding="utf-8")
    code = threejs.main(["render", "--request", str(request_path), "--result", str(result_path)])
    assert code == 0
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["schema_version"] == 1
    assert result["kind"] == "protocol"
    assert result["backend"] == THREEJS_ID

    # Support verb always writes a SupportReport (not an error).
    result = _run_protocol("support", tmp_path, _request(timeline_path))
    assert result["backend"] == THREEJS_ID
    assert result["supported"] is True
    assert "rendering.remotion" not in json.dumps(result)


# ---------------------------------------------------------------------------
# Environment preflight honesty (never a render-failure skip)
# ---------------------------------------------------------------------------


def test_threejs_support_preflight_is_honest_when_environment_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeline_path = _text_timeline(tmp_path)
    from astrid.core.rendering.contracts import RenderRequest

    request = RenderRequest.from_dict(_request(timeline_path)).for_backend(THREEJS_ID)
    monkeypatch.setattr(threejs.shutil, "which", lambda _name: None)
    report = threejs.support(request, workspace=tmp_path)
    assert report.supported is False
    assert any(
        "required binary is unavailable" in reason for reason in report.reasons
    )

    monkeypatch.undo()
    monkeypatch.setattr(
        threejs,
        "_threejs_project_reasons",
        lambda _project_dir: ["missing node_modules/three"],
    )
    report = threejs.support(request, workspace=tmp_path)
    assert report.supported is False
    assert any("node_modules/three" in reason for reason in report.reasons)


# ---------------------------------------------------------------------------
# Real renders through the public service
# ---------------------------------------------------------------------------


@pytest.mark.timeout(600)
def test_threejs_real_render_empty_timeline_through_public_service(
    tmp_path: Path,
) -> None:
    _require_threejs_environment()
    timeline_path = _empty_timeline(tmp_path)
    output = tmp_path / "threejs-empty.mp4"
    with _execution_env():
        published = render(
            timeline_path=timeline_path,
            assets_registry_path=None,
            out_path=output,
            backend=THREEJS_ID,
        )

    assert Path(published).is_file()
    assert Path(published).stat().st_size > 0
    # Checksum: the committed sidecar sha256 matches the video bytes.
    sidecar = Path(f"{published}.provenance.json")
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(Path(published).read_bytes()).hexdigest()
    # Canonical provenance keeps routing identity at the top level and
    # backend-specific details inside the namespaced fragment.
    assert payload["engine"] == THREEJS_ID
    assert payload["audio_ownership"] == "rendered"
    assert payload["routing"]["resolved_backend"] == THREEJS_ID
    assert payload["segments_v2"][0]["renderer"]["id"] == THREEJS_ID
    fragment = payload["backend_fragments"][THREEJS_ID]
    assert fragment["renderer"] == "threejs"
    assert fragment["capture_host"] == "remotion"
    assert fragment["composition"] == "ThreeTimelineComposition"
    assert fragment["renderer"] == "threejs"

    probe = _probe(published)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert video["width"] == 320 and video["height"] == 180
    assert video["avg_frame_rate"] == "24/1"
    # The video stream is exactly 1 frame (empty timeline smoke), while the
    # always-muxed AAC track pads the container.
    assert abs(float(video["duration"]) - 1.0 / 24.0) < 0.01, video
    assert any(s["codec_type"] == "audio" and s["codec_name"] == "aac" for s in probe["streams"])


@pytest.mark.timeout(600)
def test_threejs_real_render_text_timeline_through_public_service(
    tmp_path: Path,
) -> None:
    _require_threejs_environment()
    # Two clips on the same track, non-overlapping: frame 0..5 shows "A",
    # frame 6..11 shows "B" — so the render is not a uniform background.
    timeline_path = _write_timeline(
        tmp_path,
        {
            "theme": "banodoco-default",
            "theme_overrides": {
                "visual": {"canvas": dict(CANVAS), "background": "#1a1a2e"}
            },
            "tracks": [{"id": "v1", "kind": "visual", "label": "Text"}],
            "clips": [
                {
                    "id": "a",
                    "at": 0.0,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 0.25,
                    "text": {"content": "AAAA", "fontSize": 64, "color": "#ffffff"},
                },
                {
                    "id": "b",
                    "at": 0.25,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 0.25,
                    "text": {"content": "BBBB", "fontSize": 64, "color": "#ffcc00"},
                },
            ],
        },
    )
    output = tmp_path / "threejs-text.mp4"
    with _execution_env():
        published = render(
            timeline_path=timeline_path,
            assets_registry_path=None,
            out_path=output,
            backend=THREEJS_ID,
        )

    assert Path(published).is_file()
    assert Path(published).stat().st_size > 0
    probe = _probe(published)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    # Remotion's Chromium encoder emits the yuv 4:2:0 family (yuvj420p).
    assert "420p" in video["pix_fmt"], video
    assert video["width"] == 320 and video["height"] == 180
    assert video["avg_frame_rate"] == "24/1"
    assert abs(float(video["duration"]) - 0.5) < 0.1, video
    assert any(s["codec_type"] == "audio" and s["codec_name"] == "aac" for s in probe["streams"])

    # Non-uniform frame: frame 2 ("AAAA") differs from frame 8 ("BBBB").
    assert _frame_md5(published, 2) != _frame_md5(published, 8)

    sidecar = Path(f"{published}.provenance.json")
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(Path(published).read_bytes()).hexdigest()
    assert payload["engine"] == THREEJS_ID
    assert payload["audio_ownership"] == "rendered"
    assert payload["routing"]["resolved_backend"] == THREEJS_ID
    assert payload["segments_v2"][0]["renderer"]["id"] == THREEJS_ID
    assert payload["backend_fragments"][THREEJS_ID]["renderer"] == "threejs"
    assert payload["backend_fragments"][THREEJS_ID]["renderer"] == "threejs"
    assert payload["backend_fragments"][THREEJS_ID]["composition"] == "ThreeTimelineComposition"


# ---------------------------------------------------------------------------
# Shared-lock concurrency: simultaneous threejs + remotion renders serialize
# through the ONE remotion lock (no second lock).  The Three.js backend
# deliberately routes through the shared remotion execution helper, so both
# routes acquire the same non-recursive remotion_render_lock; a concurrent
# render blocks until the first releases.  Deterministic and fast: the real
# lock is exercised while the remotion CLI step is stubbed, exactly like
# test_remotion_locking.py.
# ---------------------------------------------------------------------------


def _mixed_lock_render_probe(
    lock_path: Path,
    route: str,
    name: str,
    ready: multiprocessing.synchronize.Event,
    entered: multiprocessing.synchronize.Event,
    release: multiprocessing.synchronize.Event | None,
) -> None:
    """Simulate one backend's render step while holding the real lock."""
    remotion_lock.REMOTION_LOCK_PATH = lock_path

    def fake_locked(*args: object, **kwargs: object) -> remotion_backend._ExecutionDetails:
        # The render (registry generation + remotion CLI) runs under the lock.
        assert remotion_lock.remotion_render_lock_held()
        entered.set()
        if release is not None and not release.wait(60):
            raise RuntimeError("timed out waiting to release first render")
        return remotion_backend._ExecutionDetails({}, {}, {})

    remotion_backend._execute_remotion_locked = fake_locked
    # The Three.js backend aliases the shared helper at import time
    # (threejs._execute_remotion is remotion_backend._execute_remotion); route
    # through the module each backend actually calls.
    executor = (
        threejs._execute_remotion
        if route == "threejs"
        else remotion_backend._execute_remotion
    )
    ready.set()
    executor(
        Path("timeline.json"),
        Path("assets.json"),
        Path(f"{name}.mp4"),
        provenance_out_path=Path(f"{name}.published"),
        project_dir=Path("remotion-project"),
        composition_id=(
            "ThreeTimelineComposition" if route == "threejs" else "TimelineComposition"
        ),
        theme_path=None,
        min_free_gb=None,
    )


def test_threejs_and_remotion_renders_serialize_through_one_lock(
    tmp_path: Path,
) -> None:
    # Identity: the Three.js backend uses the shared execution helper, so
    # there is exactly ONE lock acquisition point for both routes.
    assert threejs._execute_remotion is remotion_backend._execute_remotion

    context = multiprocessing.get_context("spawn")
    lock_path = tmp_path / "remotion" / ".astrid-registry.lock"
    first_ready = context.Event()
    first_entered = context.Event()
    release_first = context.Event()
    second_ready = context.Event()
    second_entered = context.Event()
    first = context.Process(
        target=_mixed_lock_render_probe,
        args=(lock_path, "threejs", "first.mp4", first_ready, first_entered, release_first),
    )
    second = context.Process(
        target=_mixed_lock_render_probe,
        args=(lock_path, "remotion", "second.mp4", second_ready, second_entered, None),
    )

    second_started = False
    first.start()
    try:
        assert first_ready.wait(60)
        assert first_entered.wait(60), "threejs render never entered the lock"
        second.start()
        second_started = True
        assert second_ready.wait(60)
        assert not second_entered.wait(0.3), (
            "remotion render entered while the threejs render held the lock"
        )
    finally:
        release_first.set()
    first.join(timeout=60)
    if second_started:
        second.join(timeout=60)
    lingering = [p for p in (first, second) if p.pid and p.is_alive()]
    for process in lingering:
        process.terminate()
        process.join(timeout=2)

    assert second_started
    assert not lingering
    assert second_entered.is_set(), "remotion render never ran after release"
    assert first.exitcode == 0
    assert second.exitcode == 0
    # No second lock: the only lock file is the one shared REMOTION_LOCK_PATH.
    assert sorted(tmp_path.rglob("*.lock")) == [lock_path]


# ---------------------------------------------------------------------------
# Offline runtime render: a real direct threejs render succeeds with npm in
# offline mode, proving no package download occurs.  npm offline mode refuses
# any fetch (ENOTCACHED/ENOTFOUND/EAI_AGAIN), so success is the proof.  The
# npm config is restored afterwards.
# ---------------------------------------------------------------------------


def _npm_offline_value() -> str:
    out = subprocess.run(
        ["npm", "config", "get", "offline"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return out


def _set_npm_offline(value: str) -> None:
    subprocess.run(
        ["npm", "config", "set", "offline", value],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.timeout(600)
def test_threejs_real_render_works_with_npm_offline(tmp_path: Path) -> None:
    """A real direct threejs render with `npm config set offline true` proves
    the runtime needs no package downloads.  The config is restored even on
    failure."""
    _require_threejs_environment()
    timeline_path = _text_timeline(tmp_path)
    output = tmp_path / "threejs-offline.mp4"

    before = _npm_offline_value()
    _set_npm_offline("true")
    try:
        with _execution_env():
            published = render(
                timeline_path=timeline_path,
                assets_registry_path=None,
                out_path=output,
                backend=THREEJS_ID,
            )
    finally:
        if before in ("null", "undefined"):
            subprocess.run(
                ["npm", "config", "delete", "offline"],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            _set_npm_offline(before)

    assert _npm_offline_value() == before, "npm offline config was not restored"
    video_path = Path(published)
    assert video_path.is_file()
    assert video_path.stat().st_size > 0
    sidecar = Path(f"{video_path}.provenance.json")
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["engine"] == THREEJS_ID
    assert payload["audio_ownership"] == "rendered"
    assert payload["backend_fragments"][THREEJS_ID]["renderer"] == "threejs"

# ---------------------------------------------------------------------------
# Batch 4 - alpha output (consumes the astrid_layer.alpha stamp)
# ---------------------------------------------------------------------------


def _threejs_stamped_timeline(tmp_path: Path, *, alpha: bool = True) -> Path:
    return _write_timeline(
        tmp_path,
        {
            "theme": "banodoco-default",
            "theme_overrides": {
                "visual": {"canvas": dict(CANVAS), "background": "#1a1a2e"}
            },
            "tracks": [{"id": "v1", "kind": "visual", "label": "Title"}],
            "clips": [
                {
                    "id": "title",
                    "at": 0.0,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 0.5,
                    "text": {"content": "ALPHA", "fontSize": 64, "color": "#ffffff"},
                    "params": {"weight": 700},
                }
            ],
            "metadata": {"astrid_layer": {"z": 1 if alpha else 0, "alpha": alpha}},
        },
    )


def _rgba_corner(video_path: Path) -> bytes:
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgba",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return raw[0:4]


def _threejs_direct_request(timeline_path: Path) -> RenderRequest:
    """A protocol-v1 request object for the Three.js backend (never a dict:
    _protocol_render is typed on RenderRequest)."""
    return RenderRequest.from_dict(
        {
            "schema_version": SCHEMA_VERSION,
            "timeline_path": str(timeline_path),
            "assets_registry_path": None,
            "output_name": "segment-0000.mp4",
            "backend_config": {},
        }
    ).for_backend(THREEJS_ID)


@pytest.mark.timeout(600)
def test_threejs_unstamped_real_render_corner_is_background_color(
    tmp_path: Path,
) -> None:
    """Unstamped (no stamp) keeps the opaque path: the corner pixel is the
    theme background #1a1a2e with alpha 255 (frozen behavior)."""
    _require_threejs_environment()
    timeline_path = _text_timeline(tmp_path)
    with _execution_env():
        threejs._protocol_render(
            _threejs_direct_request(timeline_path), workspace=tmp_path
        )
    video_path = tmp_path / "outputs" / "segment-0000.mp4"
    assert video_path.is_file() and video_path.stat().st_size > 0
    corner = _rgba_corner(video_path)
    # Frozen opaque path: the corner is the theme background #1a1a2e with
    # alpha 255.  The WebGL canvas -> yuv -> rgb round trip can land one
    # LSB off (0x19 vs 0x1A), so channels are compared with a 1-bit
    # tolerance; opacity is exact.
    assert corner[3] == 255, corner
    assert all(abs(channel - expected) <= 1 for channel, expected in zip(corner[:3], (0x1A, 0x1A, 0x2E))), corner


@pytest.mark.timeout(600)
def test_threejs_alpha_stamped_real_render_declared_profile_matches_probe(
    tmp_path: Path,
) -> None:
    """Stamped alpha through _protocol_render: strict validation passes and
    the probed artifact is the recorded batch-4-rework truth --
    mov/prores/yuva444p12le/time_base 1/90000/pcm_s16le, remapped to .mov."""
    _require_threejs_environment()
    timeline_path = _threejs_stamped_timeline(tmp_path, alpha=True)
    with _execution_env():
        result = threejs._protocol_render(
            _threejs_direct_request(timeline_path), workspace=tmp_path
        )
    video_path = tmp_path / "outputs" / "segment-0000.mov"
    assert video_path.is_file() and video_path.stat().st_size > 0
    profile = result.video.profile
    assert profile.container == "mov"
    assert profile.video_codec == "prores"
    assert profile.pixel_format == "yuva444p12le"
    assert profile.time_base == (1, 90000)
    probe = _probe(video_path)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "prores"
    assert video["pix_fmt"] == "yuva444p12le"
    assert video["time_base"] == "1/90000"
    assert any(
        s["codec_type"] == "audio" and s["codec_name"] == "pcm_s16le"
        for s in probe["streams"]
    )


@pytest.mark.timeout(600)
def test_threejs_alpha_stamped_corner_pixel_is_fully_transparent(
    tmp_path: Path,
) -> None:
    _require_threejs_environment()
    timeline_path = _threejs_stamped_timeline(tmp_path, alpha=True)
    with _execution_env():
        threejs._protocol_render(
            _threejs_direct_request(timeline_path), workspace=tmp_path
        )
    video_path = tmp_path / "outputs" / "segment-0000.mov"
    corner = _rgba_corner(video_path)
    assert corner[3] == 0, corner
