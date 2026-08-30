"""Blocking semantic parity gate for every shipped timeline renderer.

The fixtures are repository-owned JSON.  Only the tiny black H.264 video and
silent AAC audio are generated at test setup, so no binary media is committed.
Every renderer invocation below uses the production protocol transport and
``RenderService``; the ownership cases additionally cross the public executor
facade boundary.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from contextlib import nullcontext, suppress
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.execution.executor import runner as executor_runner
from astrid.core.execution.executor.registry import load_default_registry
from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor
from astrid.core.foundation import project_paths
from astrid.core.foundation.hash import sha256_file
from astrid.core.media import ffprobe_metadata_strict
from astrid.core.project.project import create_project
from astrid.core.project.run import step_dir_for, write_run_record
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    RendererErrorKind,
    RenderRequest,
)
from astrid.core.rendering.errors import (
    RendererException,
    RendererInternalError,
    RendererTimeoutError,
    exception_from_error,
    make_renderer_error,
)
from astrid.core.rendering.registry import load_default_registries
from astrid.core.rendering.service import LegacyRenderRoutingWarning, RenderService
from astrid.core.rendering.transport import CommandTransport
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.core.timeline.crud import create_timeline
from tests.packs.rendering._helpers import _execution_env

pytestmark = [pytest.mark.renderer_parity, pytest.mark.integration]

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "astrid" / "core" / "rendering" / "fixtures" / "renderer_parity"
RAW_PACK = ROOT / "tests" / "fixtures" / "renderer_packs" / "raw_command"
RAW_REQUESTS = RAW_PACK / "requests"
REMOTION = ROOT / "remotion"
CANVAS = {"width": 160, "height": 90, "fps": 10}
SEMANTIC_FIXTURES = (
    "media-only",
    "effect-clip",
    "text-card",
    "audio-reactive-colour",
    "transition-windows",
)
PARENT_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAT"
TASK_STEP_ID = "render"


@pytest.fixture(autouse=True)
def renderer_execution_environment():
    """Keep nested planner/backend commands on the test process runtime.

    The parity suite exercises real protocol subprocesses.  Their manifests
    intentionally use ``python3`` and the legacy-hybrid planner starts a
    second protocol child, so relying on the shell's ambient PATH can select a
    different interpreter that lacks the canonical timeline-schema package.
    """

    with _execution_env():
        yield


class _ParityTransport(CommandTransport):
    """Launch the real Remotion backend through the static-asset test wrapper."""

    def run(self, verb, command, **kwargs):
        backend = kwargs.get("backend") or self.backend
        if backend == "rendering.remotion":
            cwd = Path(kwargs["cwd"])
            backend_script = cwd / str(command[-1])
            command = [
                sys.executable,
                str(FIXTURES / "remotion_backend_wrapper.py"),
                backend_script,
            ]
        return super().run(verb, command, **kwargs)


def _transport_factory(backend: str) -> CommandTransport:
    return _ParityTransport(backend)


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"fixture must be a JSON object: {path}"
    return payload


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg binary is unavailable")
    assert shutil.which("ffprobe") is not None, "ffmpeg is installed but ffprobe is missing"


def _require_remotion_environment() -> None:
    """Skip real Remotion cases when the provisioned app is absent.

    Renderer support is intentionally honest about this dependency and returns
    ``supported=False``; a parity test must report the same unavailable
    environment rather than turn it into a misleading renderer failure.
    """
    if not (REMOTION / "node_modules").is_dir():
        pytest.skip("remotion/node_modules absent; real Remotion parity skipped")
    required = (
        "@banodoco/timeline-composition",
        "@banodoco/timeline-schema",
        "@banodoco/timeline-theme-2rp",
    )
    missing = [name for name in required if not (REMOTION / "node_modules" / name).is_dir()]
    if missing:
        pytest.skip("Remotion packages absent: " + ", ".join(missing))
    if shutil.which("node") is None or shutil.which("npx") is None:
        pytest.skip("node/npx absent; real Remotion parity skipped")


@pytest.fixture(scope="session")
def parity_media(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Stage semantic JSON and generate the only binary test inputs."""

    _require_ffmpeg()
    root = tmp_path_factory.mktemp("renderer-parity-media")
    shutil.copy2(FIXTURES / "assets.json", root / "assets.json")
    overrides = _json(FIXTURES / "theme-overrides.json")
    for name in (*SEMANTIC_FIXTURES, "empty"):
        payload = _json(FIXTURES / f"{name}.timeline.json")
        payload["theme_overrides"] = copy.deepcopy(overrides)
        payload["theme_overrides"]["visual"]["canvas"] = dict(CANVAS)
        (root / f"{name}.timeline.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    commands = (
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=10:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(root / "black.mp4"),
        ],
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            "2",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            str(root / "silence.m4a"),
        ],
    )
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True)
    return root


@pytest.fixture
def service(tmp_path: Path) -> RenderService:
    """Production registries plus an isolated copy of the Batch-2 raw pack."""

    extra_root = tmp_path / "extra-packs"
    extra_root.mkdir()
    shutil.copytree(RAW_PACK, extra_root / "raw_command")
    registries = load_default_registries(
        ROOT,
        extra_pack_roots=(str(extra_root),),
        include_installed=False,
    )
    return RenderService(registries=registries, transport_factory=_transport_factory)


@pytest.fixture
def remotion_static_assets(monkeypatch: pytest.MonkeyPatch):
    """Use Remotion's bundle server where this harness forbids extra sockets."""

    public_root = REMOTION / "public"
    existed = public_root.is_dir()
    public_root.mkdir(exist_ok=True)
    yield
    if not existed:
        with suppress(OSError):
            public_root.rmdir()


def _request(
    media_root: Path,
    fixture: str,
    output_name: str,
    *,
    audio: AudioOwnership | None = None,
    backend_config: dict[str, dict] | None = None,
) -> RenderRequest:
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(media_root / f"{fixture}.timeline.json"),
        assets_registry_path=str(media_root / "assets.json"),
        output_name=output_name,
        audio=audio,
        backend_config=backend_config or {},
        metadata={"fixture": fixture, "gate": "renderer-parity"},
    )


def _render(
    service: RenderService,
    media_root: Path,
    tmp_path: Path,
    fixture: str,
    selector: str,
    *,
    output_name: str | None = None,
    audio: AudioOwnership | None = None,
    backend_config: dict[str, dict] | None = None,
) -> tuple[Path, dict]:
    name = output_name or f"{fixture}-{selector.replace('.', '-')}.mp4"
    output = tmp_path / name
    result = service.render_request(
        _request(
            media_root,
            fixture,
            name,
            audio=audio,
            backend_config=backend_config,
        ),
        selector=selector,
        out_path=output,
    )
    assert result == output
    assert output.is_file() and output.stat().st_size > 0
    sidecar = Path(f"{output}.provenance.json")
    assert sidecar.is_file()
    payload = _json(sidecar)
    assert payload["output"] == str(output.resolve())
    return output, payload


def _is_managed_chromium_denial(exc: RendererException) -> bool:
    """Identify only the expected host sandbox's Chromium bootstrap denial."""

    message = str(exc)
    return (
        exc.error.kind == "internal"
        and "MachPortRendezvousServer" in message
        and "Permission denied (1100): local HTTP asset server blocked:" in message
    )


def _assert_managed_chromium_denial(exc: RendererException, output: Path) -> None:
    """Accept only the host sandbox's macOS bootstrap denial, never render errors."""

    assert _is_managed_chromium_denial(exc)
    assert not output.exists()
    assert not Path(f"{output}.provenance.json").exists()
    assert not list(output.parent.glob(f".{output.name}.render-service-*"))


@pytest.mark.parametrize(
    ("kind", "message", "expected_type"),
    (
        (
            "timeout",
            "render service failed: Timeout (>120.0s) from pytest-timeout.",
            RendererTimeoutError,
        ),
        (
            "internal",
            "render service failed: Remotion exited without producing an artifact.",
            RendererInternalError,
        ),
        (
            "internal",
            "render service failed: Permission denied (1100): unrelated renderer failure.",
            RendererInternalError,
        ),
    ),
)
def test_non_denial_renderer_errors_are_not_masked(
    kind: RendererErrorKind,
    message: str,
    expected_type: type[RendererException],
) -> None:
    """The denial compatibility path must preserve every other failure."""

    original = exception_from_error(
        make_renderer_error(
            kind,
            backend="rendering.remotion",
            message=message,
            details={"sentinel": "preserve-me"},
        )
    )
    assert isinstance(original, expected_type)
    assert not _is_managed_chromium_denial(original)

    with pytest.raises(expected_type) as caught:
        try:
            raise original
        except RendererException as exc:
            # This mirrors both Remotion call sites.  A non-denial error must
            # use a bare raise so pytest-timeout/internal details survive.
            if _is_managed_chromium_denial(exc):
                _assert_managed_chromium_denial(exc, Path("/unreachable/output.mp4"))
                return
            raise

    assert caught.value is original
    assert caught.value.error.details["sentinel"] == "preserve-me"


def _assert_tiny_semantic_video(path: Path, *, duration: float) -> None:
    probe = ffprobe_metadata_strict(path)
    assert probe.width == CANVAS["width"]
    assert probe.height == CANVAS["height"]
    # A stream-copied concat's measured avg_frame_rate lands within one frame
    # of the canonical rate (AAC-grid timestamp rounding); the planned frame
    # count is authoritative, so accept a frame-accurate tolerance.
    assert probe.fps == pytest.approx(CANVAS["fps"], abs=0.5 / duration)
    assert probe.duration_seconds == pytest.approx(duration, abs=0.12)


def _visual_only_fixture(parity_media: Path, tmp_path: Path) -> Path:
    root = tmp_path / "visual-only"
    root.mkdir()
    for name in ("assets.json", "black.mp4", "silence.m4a"):
        shutil.copy2(parity_media / name, root / name)
    timeline = _json(parity_media / "media-only.timeline.json")
    timeline["tracks"] = [track for track in timeline["tracks"] if track["kind"] == "visual"]
    timeline["clips"] = [clip for clip in timeline["clips"] if clip["track"] == "source"]
    (root / "visual-only.timeline.json").write_text(
        json.dumps(timeline, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def test_repository_fixtures_are_populated_and_reuse_default_theme_golden() -> None:
    for name in SEMANTIC_FIXTURES:
        payload = _json(FIXTURES / f"{name}.timeline.json")
        assert payload.get("tracks"), f"semantic fixture has no tracks: {name}"
        assert payload.get("clips"), f"semantic fixture has no clips: {name}"
    empty = _json(FIXTURES / "empty.timeline.json")
    assert empty["tracks"] == [] and empty["clips"] == []

    overrides = _json(FIXTURES / "theme-overrides.json")
    golden = _json(ROOT / "tests" / "golden" / "hype" / "merged_render_props.json")
    assert overrides["visual"] == golden["theme"]["visual"]


def test_empty_timeline_is_rejected_and_failure_workspace_is_clean(
    service: RenderService,
    tmp_path: Path,
) -> None:
    output = tmp_path / "empty.mp4"
    request = RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(FIXTURES / "empty.timeline.json"),
        assets_registry_path=str(FIXTURES / "assets.json"),
        output_name=output.name,
        backend_config={},
    )
    with pytest.raises(RendererException) as caught:
        service.render_request(request, selector="hybrid", out_path=output)
    assert caught.value.error.kind == "unsupported"
    assert not output.exists()
    assert not Path(f"{output}.provenance.json").exists()
    assert not list(tmp_path.glob(".*.render-service-*"))


@pytest.mark.parametrize("fixture", SEMANTIC_FIXTURES)
def test_real_remotion_renders_each_semantic_variant(
    fixture: str,
    parity_media: Path,
    service: RenderService,
    tmp_path: Path,
    remotion_static_assets: None,
) -> None:
    _require_remotion_environment()
    expected_output = tmp_path / f"{fixture}-rendering-remotion.mp4"
    try:
        output, sidecar = _render(
            service,
            parity_media,
            tmp_path,
            fixture,
            "rendering.remotion",
            audio=AudioOwnership.RENDERED,
            backend_config={
                "rendering.remotion": {
                    "project_dir": str(REMOTION),
                    "composition_id": "TimelineComposition",
                }
            },
        )
    except RendererException as exc:
        if not _is_managed_chromium_denial(exc):
            raise
        _assert_managed_chromium_denial(exc, expected_output)
        return
    duration = 2.0 if fixture == "transition-windows" else 0.6
    _assert_tiny_semantic_video(output, duration=duration)
    routing = sidecar["routing"]
    assert routing["requested_engine"] == "rendering.remotion"
    assert routing["resolved_backends"] == ["rendering.remotion"]
    assert sidecar["audio_ownership"] == "rendered"


@pytest.mark.parametrize("fixture", ("media-only", "audio-reactive-colour"))
def test_real_ffmpeg_renders_supported_semantic_variants(
    fixture: str,
    parity_media: Path,
    service: RenderService,
    tmp_path: Path,
) -> None:
    output, sidecar = _render(
        service,
        parity_media,
        tmp_path,
        fixture,
        "rendering.ffmpeg",
        audio=AudioOwnership.RENDERED,
    )
    _assert_tiny_semantic_video(output, duration=0.6)
    assert sidecar["routing"]["resolved_backends"] == ["rendering.ffmpeg"]
    assert sidecar["audio_ownership"] == "rendered"
    if fixture == "audio-reactive-colour":
        fragment = sidecar["backend_fragments"]["rendering.ffmpeg"]
        assert fragment["specialization"]["id"] == "audio-reactive-colour/v1"


def test_nominal_remotion_auto_routes_supported_media_to_ffmpeg(
    parity_media: Path,
    service: RenderService,
    tmp_path: Path,
) -> None:
    with pytest.warns(LegacyRenderRoutingWarning):
        output, sidecar = _render(
            service,
            parity_media,
            tmp_path,
            "media-only",
            "remotion",
            audio=AudioOwnership.RENDERED,
        )
    _assert_tiny_semantic_video(output, duration=0.6)
    assert sidecar["routing"]["auto_route"] is True
    assert sidecar["routing"]["resolved_backends"] == ["rendering.ffmpeg"]


def test_real_all_ffmpeg_hybrid_plans_and_finalizes(
    parity_media: Path,
    service: RenderService,
    tmp_path: Path,
) -> None:
    output, sidecar = _render(
        service,
        parity_media,
        tmp_path,
        "media-only",
        "hybrid",
        audio=AudioOwnership.RENDERED,
        backend_config={
            "rendering.legacy_hybrid": {"renderers": ["rendering.ffmpeg"]}
        },
    )
    _assert_tiny_semantic_video(output, duration=0.6)
    assert [segment["renderer"]["id"] for segment in sidecar["segments_v2"]] == [
        "rendering.ffmpeg"
    ]
    assert sidecar["finalizer"]["id"] == "rendering.ffmpeg-finalizer"


def test_real_mixed_hybrid_uses_transition_windows(
    parity_media: Path,
    service: RenderService,
    tmp_path: Path,
    remotion_static_assets: None,
) -> None:
    _require_remotion_environment()
    expected_output = tmp_path / "transition-windows-hybrid.mp4"
    try:
        output, sidecar = _render(
            service,
            parity_media,
            tmp_path,
            "transition-windows",
            "hybrid",
            audio=AudioOwnership.RENDERED,
            backend_config={
                "rendering.legacy_hybrid": {
                    "simple_renderers": ["rendering.ffmpeg"],
                    "complex_renderers": ["rendering.remotion"],
                },
                "rendering.remotion": {
                    "project_dir": str(REMOTION),
                    "composition_id": "TimelineComposition",
                },
            },
        )
    except RendererException as exc:
        if not _is_managed_chromium_denial(exc):
            raise
        _assert_managed_chromium_denial(exc, expected_output)
        return
    _assert_tiny_semantic_video(output, duration=2.0)
    segments = sidecar["segments_v2"]
    assert [segment["renderer"]["id"] for segment in segments] == [
        "rendering.remotion",
        "rendering.ffmpeg",
    ]
    windows = [segment["window"] for segment in segments]
    assert windows[0]["start_frame"] == 0
    assert windows[-1]["end_frame"] == 20
    assert all(
        left["end_frame"] == right["start_frame"]
        for left, right in zip(windows, windows[1:])
    )
    assert sidecar["finalizer"]["id"] == "rendering.ffmpeg-finalizer"


def test_raw_fixture_renderer_is_real_deterministic_and_honors_output_names(
    parity_media: Path,
    service: RenderService,
    tmp_path: Path,
) -> None:
    outputs: list[Path] = []
    for name in ("hype.mp4", "parity.mp4"):
        output, sidecar = _render(
            service,
            parity_media,
            tmp_path,
            "media-only",
            "raw_command.renderer",
            output_name=name,
            audio=AudioOwnership.RENDERED,
            backend_config={"raw_command.renderer": {"mode": "solid"}},
        )
        outputs.append(output)
        assert sidecar["routing"]["resolved_backends"] == ["raw_command.renderer"]
        assert sidecar["audio_ownership"] == "rendered"
    assert sha256_file(outputs[0]) == sha256_file(outputs[1])


def test_audio_none_is_published_but_passthrough_requires_host_completion(
    parity_media: Path,
    service: RenderService,
    tmp_path: Path,
) -> None:
    visual_root = _visual_only_fixture(parity_media, tmp_path)
    output, sidecar = _render(
        service,
        visual_root,
        tmp_path,
        "visual-only",
        "rendering.ffmpeg",
        output_name="visual-only.mp4",
        audio=AudioOwnership.NONE,
    )
    probe = ffprobe_metadata_strict(output)
    assert probe.has_audio_stream is False
    assert sidecar["audio_ownership"] == "none"

    passthrough = tmp_path / "passthrough.mp4"
    with pytest.raises(RendererException) as caught:
        service.render_request(
            _request(
                visual_root,
                "visual-only",
                passthrough.name,
                audio=AudioOwnership.PASSTHROUGH,
            ),
            selector="rendering.ffmpeg",
            out_path=passthrough,
        )
    assert caught.value.error.kind == "unsupported"
    assert not passthrough.exists()
    assert not Path(f"{passthrough}.provenance.json").exists()
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_real_raw_artifact_with_tampered_bytes_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "raw-invalid"
    workspace.mkdir()
    shutil.copy2(RAW_REQUESTS / "timeline.json", workspace / "timeline.json")
    request_path = workspace / "request.json"
    request_path.write_text(
        (RAW_REQUESTS / "render.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result_path = workspace / "result.json"
    result = CommandTransport("raw_command.renderer").run(
        "render",
        [sys.executable, "backend.py"],
        request_path=request_path,
        result_path=result_path,
        cwd=RAW_PACK,
        timeout=30,
    )
    artifact = workspace / result.video.path
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    with pytest.raises(RendererException) as caught:
        validate_render_result(
            result,
            expected_profile=result.video.profile,
            workspace_root=workspace,
        )
    assert caught.value.error.kind == "invalid_artifact"


def _clear_task_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ASTRID_SESSION_ID",
        "ASTRID_PROJECT_RUN",
        "ASTRID_TASK_RUN_ID",
        "ASTRID_TASK_PROJECT",
        "ASTRID_TASK_STEP_ID",
        "ASTRID_TASK_ITEM_ID",
        "ASTRID_TASK_ITERATION",
        "ASTRID_RUN_ID",
        "ASTRID_PARENT_RUN_ID",
    ):
        monkeypatch.delenv(name, raising=False)


def _fake_render_process(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv, **_kwargs) -> int:
        arguments = [str(item) for item in argv]
        out = Path(arguments[arguments.index("--out") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"facade-boundary-mp4")
        Path(f"{out}.provenance.json").write_text("{}", encoding="utf-8")
        return 0

    monkeypatch.setattr(executor_runner, "run_subprocess_with_capture", fake_run)
    monkeypatch.setattr(
        executor_runner,
        "open_run_log_capture",
        lambda *_args, **_kwargs: nullcontext(SimpleNamespace(stdout=None, stderr=None)),
    )


@pytest.mark.parametrize(
    ("attached", "output_name"),
    ((False, "hype.mp4"), (True, "attached-parity.mp4")),
)
def test_public_facade_standalone_and_attached_run_ownership(
    attached: bool,
    output_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    parity_media: Path,
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_task_env(monkeypatch)
    create_project("demo")
    timeline_record = create_timeline("demo", "main", is_default=True)
    inputs_root = projects_root / "demo" / "inputs"
    inputs_root.mkdir(parents=True)
    timeline = inputs_root / "hype.timeline.json"
    assets = inputs_root / "hype.assets.json"
    # The ownership assertion must reach the runner's staging boundary with a
    # renderer-valid request; an empty timeline is correctly rejected before
    # the fake child process can exercise ownership behavior.
    shutil.copy2(parity_media / "media-only.timeline.json", timeline)
    shutil.copy2(parity_media / "assets.json", assets)
    shutil.copy2(parity_media / "black.mp4", inputs_root / "black.mp4")
    shutil.copy2(parity_media / "silence.m4a", inputs_root / "silence.m4a")
    inputs = {
        "timeline": str(timeline),
        "assets_registry": str(assets),
        "engine": "ffmpeg",
        "output_name": output_name,
    }
    _fake_render_process(monkeypatch)

    if attached:
        write_run_record(
            "demo",
            PARENT_RUN_ID,
            kind="task",
            status="running",
            timeline_id=timeline_record["ulid"],
        )
        monkeypatch.setenv(TASK_PROJECT_ENV, "demo")
        monkeypatch.setenv(TASK_RUN_ID_ENV, PARENT_RUN_ID)
        monkeypatch.setenv(TASK_STEP_ID_ENV, TASK_STEP_ID)

    # ``run_executor`` is the lower-level capability runner.  Kernel-backed
    # SDK invocation supplies its private staging root before reaching this
    # seam; direct callers must provide the equivalent staging path.  Keeping
    # this explicit prevents the test from asserting the retired runner-owned
    # run.json ledger behavior.
    if attached:
        staging_root = step_dir_for(
            "demo",
            PARENT_RUN_ID,
            TASK_STEP_ID,
            step_version=1,
            root=projects_root,
        )
    else:
        staging_root = tmp_path / "standalone-render-staging"

    result = run_executor(
        ExecutorRunRequest(
            executor_id="rendering.render",
            out=staging_root,
            project="demo",
            inputs=inputs,
            project_was_auto_resolved=True,
            run_root=staging_root,
        ),
        load_default_registry(),
    )
    assert result.returncode == 0
    run_jsons = sorted((projects_root / "demo" / "runs").glob("**/run.json"))
    if attached:
        expected_parent = projects_root / "demo" / "runs" / PARENT_RUN_ID / "run.json"
        assert run_jsons == [expected_parent]
        assert result.run_root == staging_root
        assert not (staging_root / "run.json").exists()
    else:
        assert run_jsons == []
        assert result.run_root == staging_root
    assert (result.run_root / output_name).is_file()


def test_remotion_typecheck_is_blocking_when_dependencies_are_installed() -> None:
    if not (REMOTION / "node_modules").is_dir():
        return
    assert shutil.which("node") is not None, "remotion/node_modules exists but node is missing"
    assert shutil.which("npm") is not None, "remotion/node_modules exists but npm is missing"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gen_remotion_types.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        ["npm", "run", "typecheck"],
        cwd=REMOTION,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        "Remotion typecheck failed:\n" + completed.stdout + "\n" + completed.stderr
    )
