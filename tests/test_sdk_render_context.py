"""T6.3 — RenderContext facade for third-party ``render.py`` authors.

Locks the convenience facade in :mod:`astrid.sdk.rendering.RenderContext`:

* workspace-validated path allocation (inside accepted, outside rejected);
* asset descriptors resolve to absolute staged files or the invocation
  asset server URL;
* sanitized subprocess runner: scrubbed env, bounded redacted output, hard
  timeout, no shell;
* redacted logs/progress (secret env values + registry tokens);
* cooperative interruption flag raising the frozen ``interrupted`` error;
* probe/hash/audio-completion/attachments round-trip through the core
  primitives;
* crash-safe ``__exit__`` cleanup of temp dirs even when the body raises.

Run: ``pytest -q tests/test_sdk_render_context.py``
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

import pytest

from astrid.core import timeline
from astrid.core.media import MediaProbe
from astrid.core.rendering.assets import AssetMaterializer, InvocationAssetServer
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    FinalizerResolution,
    FrameWindow,
    PlannerResolution,
    RenderPlan,
    RenderProfile,
    RenderRequest,
    RenderResult,
    RenderSegment,
    RendererResolution,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.errors import (
    RendererInterruptedError,
    RendererInternalError,
    RendererTimeoutError,
    RendererUnsupportedError,
)
from astrid.core.rendering.registry import (
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
)
from astrid.core.rendering.service import RenderService
from astrid.core.subprocess_env import SubprocessEnvPolicyError

from astrid.sdk.rendering import RenderContext


def _profile() -> RenderProfile:
    """A visual-only (no-audio) canonical profile."""
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


def _audio_profile() -> RenderProfile:
    """The visual profile plus host-completed AAC audio fields."""
    return dataclasses.replace(
        _profile(),
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channel_layout="stereo",
    )


def _support(backend: str) -> SupportReport:
    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=True,
        reasons=[],
        features={},
        alternatives=[],
        backend=backend,
        backend_version="1.0.0",
    )


def _renderer_resolution(backend: str) -> RendererResolution:
    return RendererResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest="0" * 64,
        alias_chain=[],
        override=None,
        support_decision=_support(backend),
        trust_eligibility={"eligible": True},
    )


def _planner_resolution(backend: str) -> PlannerResolution:
    return PlannerResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest="0" * 64,
        trust_eligibility={"eligible": True},
    )


def _finalizer_resolution(backend: str) -> FinalizerResolution:
    return FinalizerResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest="0" * 64,
        trust_eligibility={"eligible": True},
    )


def _plan() -> RenderPlan:
    """A minimal deterministic render plan (10 frames, single segment)."""
    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest="0" * 64,
        requested_policy="hybrid",
        planner=_planner_resolution("rendering.legacy_hybrid"),
        segments=[
            RenderSegment(
                window=FrameWindow(start_frame=0, end_frame=10, fps_rational=(10, 1)),
                renderer=_renderer_resolution("fixture.renderer"),
                input_hashes={},
            )
        ],
        finalizer=_finalizer_resolution("rendering.ffmpeg-finalizer"),
        profile=_profile(),
        total_frames=10,
        reasons={"0": "fixture"},
    )


def _request(workspace: Path) -> RenderRequest:
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(workspace / "timeline.json"),
        output_name="video.mp4",
    )


def _render_result(
    workspace: Path,
    *,
    ownership: AudioOwnership,
    profile: RenderProfile,
) -> RenderResult:
    video_path = workspace / "outputs" / "video.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"fixture-video")
    video = VideoArtifact.from_file(
        path=video_path,
        workspace_root=workspace,
        profile=profile,
        duration_frames=10,
        audio=ownership,
    )
    return RenderResult(
        schema_version=SCHEMA_VERSION,
        video=video,
        audio_ownership=ownership,
        backend_fragments={"fixture.renderer": {"fixture": True}},
    )


def _write_registry(path: Path, assets: dict[str, dict[str, object]]) -> Path:
    timeline.save_registry({"assets": assets}, path)
    return path


# ---------------------------------------------------------------------------
# Paths — allocated inside workspace, rejected outside
# ---------------------------------------------------------------------------


def test_paths_allocated_inside_workspace_and_outside_rejected(tmp_path: Path) -> None:
    with RenderContext(tmp_path / "workspace") as ctx:
        assert ctx.workspace == (tmp_path / "workspace").resolve()
        assert ctx.workspace.is_dir()

        output = ctx.output_path("video.mp4")
        assert output == ctx.outputs_dir / "video.mp4"
        assert output.is_absolute()
        assert output.parent.is_dir()

        frames = ctx.workspace_path("frames/f0001.png")
        assert frames == (ctx.workspace / "frames" / "f0001.png").resolve()
        assert frames.parent.is_dir()

        # Outside-the-workspace and malformed paths are rejected.
        for bad in (
            "../escape.bin",
            "/etc/passwd",
            "a\\b",
            "a/../b",
            "nested//x",
            "..",
        ):
            with pytest.raises(ValueError):
                ctx.workspace_path(bad)
        with pytest.raises(ValueError):
            ctx.output_path("../escape.mp4")
        with pytest.raises(ValueError):
            ctx.output_path("dir/video.mp4")
        with pytest.raises(ValueError):
            ctx.output_path("")

    # check_path: outside the workspace is rejected unless explicitly allowed.
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside_allowed = allowed / "inside.bin"
    inside_allowed.write_bytes(b"allowed")

    with RenderContext(tmp_path / "workspace2") as ctx:
        with pytest.raises(ValueError):
            ctx.check_path(outside)
        assert ctx.check_path(ctx.workspace / "ok.bin") == (ctx.workspace / "ok.bin").resolve()

    with RenderContext(tmp_path / "workspace3", allowed_roots=(allowed,)) as ctx:
        assert ctx.check_path(inside_allowed) == inside_allowed.resolve()


# ---------------------------------------------------------------------------
# Assets — absolute staged file and invocation asset server URL
# ---------------------------------------------------------------------------


def test_asset_descriptor_resolves_to_absolute_file_and_server_url(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"local asset bytes")
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"main": {"file": source.name, "type": "application/octet-stream"}},
    )
    workspace = tmp_path / "workspace"

    with AssetMaterializer(registry_path) as materializer:
        with InvocationAssetServer(materializer.staging_dir) as server:
            with RenderContext(
                workspace,
                materializer=materializer,
                asset_server=server,
            ) as ctx:
                staged = ctx.asset_path("main")
                assert staged.is_absolute()
                assert staged != source
                assert staged.read_bytes() == b"local asset bytes"

                url = ctx.asset_url("main")
                assert url.startswith("http://127.0.0.1:")
                with urllib.request.urlopen(url, timeout=5) as response:
                    assert response.read() == b"local asset bytes"

                resolved = ctx.resolved_registry()
                assert resolved["assets"]["main"]["file"] == url

                with pytest.raises(ValueError):
                    ctx.asset_path("missing")
                with pytest.raises(ValueError):
                    ctx.asset_url("missing")

    # A context without a materializer cannot resolve asset descriptors.
    with RenderContext(tmp_path / "workspace2") as ctx:
        with pytest.raises(ValueError):
            ctx.asset_path("main")
        with pytest.raises(ValueError):
            ctx.resolved_registry()


# ---------------------------------------------------------------------------
# Subprocess runner — scrubbed env, timeout, no shell
# ---------------------------------------------------------------------------


def test_subprocess_env_scrubbed_timeout_enforced_no_shell_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MY_RENDER_TOKEN", "super-secret-token-123")
    with RenderContext(tmp_path / "workspace") as ctx:
        # Secret-named host variables never reach the child environment.
        result = ctx.run(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ.get('MY_RENDER_TOKEN', 'MISSING'))",
            ]
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "MISSING"

        # Secret-named explicit entries must use the host's declared secret
        # channel; accepting them as ordinary env would bypass the policy.
        with pytest.raises(SubprocessEnvPolicyError, match="secret env"):
            ctx.run(
                [
                    sys.executable,
                    "-c",
                    "import os; print(os.environ.get('MY_FFMPEG_TOKEN', 'MISSING'))",
                ],
                env={"MY_FFMPEG_TOKEN": "ffmpeg-token-abc"},
            )

        # No shell by default: "$HOME" is passed literally, not expanded.
        result = ctx.run(["echo", "$HOME"])
        assert result.returncode == 0
        assert result.stdout.strip() == "$HOME"

        # Timeout is enforced and raises the frozen timeout error.
        with pytest.raises(RendererTimeoutError) as excinfo:
            ctx.run(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                timeout=0.3,
            )
        assert excinfo.value.error.kind == "timeout"
        assert excinfo.value.error.backend == "astrid.core"

        # Non-zero exit raises the frozen internal error when check=True.
        with pytest.raises(RendererInternalError) as excinfo:
            ctx.run([sys.executable, "-c", "import sys; sys.exit(3)"])
        assert excinfo.value.error.kind == "internal"

        # check=False returns the bounded result instead.
        result = ctx.run(
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            check=False,
        )
        assert result.returncode == 3


# ---------------------------------------------------------------------------
# Redacted logs / progress
# ---------------------------------------------------------------------------


def test_logs_redact_secret_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRID_REGISTRY_TOKEN", "registry-token-xyz")
    with RenderContext(tmp_path / "workspace", secret_values=("extra-secret-42",)) as ctx:
        ctx.log("uploading registry-token-xyz with extra-secret-42 attached")
        assert "registry-token-xyz" not in ctx.logs[0]
        assert "extra-secret-42" not in ctx.logs[0]
        assert "[redacted]" in ctx.logs[0]

        ctx.progress("progress registry-token-xyz")
        assert "registry-token-xyz" not in ctx.logs[1]

        redacted = ctx.redact("Authorization: Bearer sk-test-abcdefghijkl")
        assert "sk-test-abcdefghijkl" not in redacted
        assert "[redacted]" in redacted

        bearer = ctx.redact("signing with Bearer ghp_abcdefghijklmnop")
        assert "ghp_abcdefghijklmnop" not in bearer
        assert "Bearer [redacted]" in bearer


# ---------------------------------------------------------------------------
# Interruption state
# ---------------------------------------------------------------------------


def test_interruption_flag_raises_frozen_error(tmp_path: Path) -> None:
    cancelled = {"flag": False}
    with RenderContext(
        tmp_path / "workspace",
        interrupt_check=lambda: cancelled["flag"],
    ) as ctx:
        assert ctx.interrupt_requested is False
        ctx.raise_if_interrupted()  # no-op while not cancelled

        cancelled["flag"] = True
        assert ctx.interrupt_requested is True
        with pytest.raises(RendererInterruptedError) as excinfo:
            ctx.raise_if_interrupted()
        assert excinfo.value.error.kind == "interrupted"
        assert excinfo.value.error.backend == "astrid.core"


# ---------------------------------------------------------------------------
# Probe / hash / audio completion / attachments round-trip
# ---------------------------------------------------------------------------


def test_probe_hash_audio_completion_and_attachments_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    seen: dict[str, object] = {}

    def fake_completer(
        result: RenderResult,
        *,
        request: RenderRequest,
        plan: RenderPlan,
        workspace: Path,
    ) -> RenderResult:
        seen["request"] = request
        seen["plan"] = plan
        seen["workspace"] = workspace
        video = dataclasses.replace(
            result.video,
            audio=AudioOwnership.RENDERED,
            profile=_audio_profile(),
        )
        return dataclasses.replace(
            result,
            video=video,
            audio_ownership=AudioOwnership.RENDERED,
        )

    service = RenderService(
        registries=(RendererRegistry([]), PlannerRegistry([]), FinalizerRegistry([])),
        validator=lambda result, **_kwargs: result,
        audio_completer=fake_completer,
    )
    probe = MediaProbe(
        duration_seconds=1.0,
        fps=10.0,
        resolution="160x90",
        width=160,
        height=90,
        fps_rational=(10, 1),
        time_base=(1, 10240),
        video_codec="h264",
        container="mp4",
    )
    monkeypatch.setattr(
        "astrid.core.media.ffprobe_metadata_strict",
        lambda path: probe,
    )

    request = _request(workspace)
    plan = _plan()
    payload = b"poster-bytes"
    hashed = hashlib.sha256(payload).hexdigest()
    media_file = workspace / "probe.mp4"
    workspace.mkdir(parents=True, exist_ok=True)
    media_file.write_bytes(b"probe-bytes")

    with RenderContext(workspace, service=service) as ctx:
        # Probe wrapper delegates to ffprobe_metadata_strict.
        media = ctx.probe_media(media_file)
        assert media is probe
        assert media.video_codec == "h264"

        # Hash wrapper delegates to sha256_file.
        digest = ctx.sha256(media_file)
        assert digest == hashlib.sha256(b"probe-bytes").hexdigest()

        # Attachments: named byte payloads validated by the frozen contract.
        attachment = ctx.add_attachment("poster.png", payload, kind="poster")
        assert attachment.name == "poster.png"
        assert attachment.kind == "poster"
        assert attachment.sha256 == hashed
        assert attachment.path == "attachments/poster.png"
        stored = workspace / "attachments" / "poster.png"
        assert stored.read_bytes() == payload
        assert ctx.attachments == {"poster.png": attachment}
        with pytest.raises(ValueError):
            ctx.add_attachment("bad/name", payload)
        with pytest.raises(TypeError):
            ctx.add_attachment("bad.bin", "not-bytes")

        # Audio completion calls the core complete_audio helper.
        result = _render_result(
            workspace,
            ownership=AudioOwnership.PASSTHROUGH,
            profile=_profile(),
        )
        completed = ctx.complete_audio(result, request=request, plan=plan)
        assert completed.audio_ownership is AudioOwnership.RENDERED
        assert completed.video.profile.has_audio is True
        assert result.audio_ownership is AudioOwnership.PASSTHROUGH
        assert seen["request"] is request
        assert seen["plan"] is plan
        assert seen["workspace"] == workspace

    # Without a service or completer, audio completion is unsupported.
    with RenderContext(tmp_path / "workspace2") as ctx:
        result = _render_result(
            tmp_path / "workspace2",
            ownership=AudioOwnership.PASSTHROUGH,
            profile=_profile(),
        )
        with pytest.raises(RendererUnsupportedError) as excinfo:
            ctx.complete_audio(result, request=_request(tmp_path / "workspace2"))
        assert excinfo.value.error.kind == "unsupported"


# ---------------------------------------------------------------------------
# Cleanup — temp dirs removed even on exception (crash-safe)
# ---------------------------------------------------------------------------


def test_exit_cleans_temp_dirs_on_normal_exit(tmp_path: Path) -> None:
    with RenderContext(tmp_path / "workspace") as ctx:
        first = ctx.temp_dir("scratch-")
        second = ctx.temp_dir()
        assert first.is_dir()
        assert second.is_dir()
        temp_root = ctx.workspace / ".astrid-tmp"
        assert temp_root.is_dir()

    assert not first.exists()
    assert not second.exists()
    assert not temp_root.exists()
    assert ctx._closed is True


def test_exit_cleans_temp_dirs_when_body_raises(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    try:
        with RenderContext(workspace) as ctx:
            scratch = ctx.temp_dir()
            assert scratch.is_dir()
            raise ValueError("crash")
    except ValueError:
        pass
    assert not scratch.exists()
    assert not (workspace / ".astrid-tmp").exists()
    assert ctx._closed is True
