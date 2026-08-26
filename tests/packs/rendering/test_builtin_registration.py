from __future__ import annotations

import builtins
import importlib
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from unittest import mock

import pytest

from astrid.core.media import ffprobe_metadata_strict
from astrid.core.pack.validate import validate_pack
from astrid.core.rendering.contracts import SCHEMA_VERSION, RenderRequest, RenderResult
from astrid.core.rendering.registry import load_default_registries
from astrid.core.rendering.transport import CommandTransport

ROOT = Path(__file__).resolve().parents[3]
RENDERING_PACK = ROOT / "astrid" / "packs" / "rendering"
REMOTION_PROJECT = ROOT / "remotion"
BACKEND_MODULE_PREFIXES = (
    "astrid.packs.rendering.backends.remotion",
    "astrid.packs.rendering.backends.ffmpeg",
    "astrid.packs.rendering.finalizers.ffmpeg",
)


def _registries():
    return load_default_registries(ROOT, include_installed=False)


def _write_media_timeline(
    root: Path,
    source: Path,
    *,
    duration: float,
    width: int = 160,
    height: int = 90,
    fps: int = 10,
) -> tuple[Path, Path]:
    timeline_path = root / "timeline.json"
    assets_path = root / "assets.json"
    timeline_path.write_text(
        json.dumps(
            {
                "theme": "banodoco-default",
                "theme_overrides": {
                    "visual": {
                        "canvas": {"width": width, "height": height, "fps": fps}
                    }
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
                        "to": duration,
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
                        "duration": duration,
                        "resolution": f"{width}x{height}",
                        "fps": fps,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return timeline_path, assets_path


def _request(
    timeline_path: Path,
    assets_path: Path,
    *,
    backend: str,
    output_name: str,
    backend_settings: dict[str, str] | None = None,
) -> RenderRequest:
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name=output_name,
        backend_config={backend: backend_settings or {}},
    )


def _write_request(path: Path, request: RenderRequest) -> None:
    path.write_text(json.dumps(request.to_dict()), encoding="utf-8")


def _missing_remotion_dependencies() -> list[str]:
    missing = [
        f"{binary} executable"
        for binary in ("ffprobe",)
        if shutil.which(binary) is None
    ]
    node = os.environ.get("ASTRID_NODE_EXECUTABLE", "").strip()
    if not node or not Path(node).is_file():
        missing.append("ASTRID_NODE_EXECUTABLE")
    if not (REMOTION_PROJECT / "node_modules").is_dir():
        missing.append("remotion/node_modules")
    if not (
        REMOTION_PROJECT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    ).is_file():
        missing.append("remotion local CLI")
    return missing


def test_rendering_pack_and_builtin_manifests_validate() -> None:
    errors, _warnings = validate_pack(RENDERING_PACK)

    assert errors == []


def test_builtin_registration_and_inspection_are_static(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASTRID_PACKS_PATH", raising=False)
    real_import = builtins.__import__

    def reject_backend_import(
        name: str,
        globals=None,
        locals=None,
        fromlist=(),
        level: int = 0,
    ):
        assert not name.startswith(BACKEND_MODULE_PREFIXES), (
            f"static registry inspection imported backend code: {name}"
        )
        return real_import(name, globals, locals, fromlist, level)

    with (
        mock.patch.object(builtins, "__import__", side_effect=reject_backend_import),
        mock.patch.object(
            importlib,
            "import_module",
            side_effect=AssertionError("static inspection attempted a dynamic import"),
        ),
        mock.patch.object(
            subprocess,
            "Popen",
            side_effect=AssertionError("static inspection attempted backend execution"),
        ),
    ):
        renderers, planners, finalizers = _registries()
        remotion = renderers.inspect("rendering.remotion")
        ffmpeg = renderers.inspect("rendering.ffmpeg")
        ffmpeg_finalizer = finalizers.inspect("rendering.ffmpeg-finalizer")
        resolved = (
            renderers.get("rendering.remotion"),
            renderers.get("rendering.ffmpeg"),
            finalizers.get("rendering.ffmpeg-finalizer"),
        )

    assert [candidate.id for candidate in planners.list()] == [
        "rendering.layer-stack",
        "rendering.legacy_hybrid",
        "rendering.threejs-hybrid",
    ]
    assert remotion == (resolved[0],)
    assert ffmpeg == (resolved[1],)
    assert ffmpeg_finalizer == (resolved[2],)
    assert [candidate.id for candidate in resolved] == [
        "rendering.remotion",
        "rendering.ffmpeg",
        "rendering.ffmpeg-finalizer",
    ]
    assert [candidate.manifest.required_binaries for candidate in resolved] == [
        ("ffprobe",),
        ("ffmpeg", "ffprobe"),
        ("ffmpeg", "ffprobe"),
    ]
    for candidate in resolved:
        assert candidate.pack_id == "rendering"
        assert candidate.source_kind == "source"
        assert candidate.execution_eligible is True
        assert candidate.manifest.command == ("python3", "run.py")
        assert (candidate.pack_root / candidate.manifest.command[1]).is_file()


def test_real_ffmpeg_render_through_registered_backend(tmp_path: Path) -> None:
    assert shutil.which("ffmpeg") is not None, (
        "required FFmpeg smoke dependency is unavailable: ffmpeg executable"
    )
    assert shutil.which("ffprobe") is not None, (
        "required FFmpeg smoke dependency is unavailable: ffprobe executable"
    )
    source_path = tmp_path / "source.mp4"
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
            str(source_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    timeline_path, assets_path = _write_media_timeline(
        tmp_path,
        source_path,
        duration=0.5,
    )
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request = _request(
        timeline_path,
        assets_path,
        backend="rendering.ffmpeg",
        output_name="ffmpeg-smoke.mp4",
    )
    _write_request(request_path, request)
    renderers, _planners, _finalizers = _registries()
    candidate = renderers.get("rendering.ffmpeg")

    result = CommandTransport(candidate.id).run(
        "render",
        candidate.manifest.command,
        request_path=request_path,
        result_path=result_path,
        cwd=candidate.pack_root,
        required_binaries=candidate.manifest.required_binaries,
    )

    assert isinstance(result, RenderResult)
    video_path = tmp_path / result.video.path
    assert video_path.is_file()
    assert video_path.stat().st_size > 0
    assert result.video.duration_frames == 5
    assert result.backend_fragments["rendering.ffmpeg"]["renderer"] == "ffmpeg"
    probe = ffprobe_metadata_strict(video_path)
    assert probe.has_video_stream is True
    assert probe.width == 160
    assert probe.height == 90
    assert probe.duration_seconds is not None and probe.duration_seconds > 0
    assert not list(tmp_path.glob(".ffmpeg-smoke.mp4.*"))


def test_real_remotion_render_through_registered_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = _missing_remotion_dependencies()
    if missing:
        pytest.skip(
            "Remotion backend smoke skipped: missing optional dependencies: "
            + ", ".join(missing)
        )

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        missing_media = [
            f"{binary} executable"
            for binary, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe))
            if path is None
        ]
        pytest.skip(
            "Remotion backend smoke skipped: missing optional media dependencies: "
            + ", ".join(missing_media)
        )

    source_path = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=160x90:r=10:d=0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(source_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    timeline_path, assets_path = _write_media_timeline(
        tmp_path,
        source_path,
        duration=0.5,
    )
    request = _request(
        timeline_path,
        assets_path,
        backend="rendering.remotion",
        output_name="remotion-smoke.mp4",
        backend_settings={"project_dir": str(REMOTION_PROJECT)},
    )
    renderers, _planners, _finalizers = _registries()
    candidate = renderers.get("rendering.remotion")

    remotion_backend = importlib.import_module(
        "astrid.packs.rendering.backends.remotion.run"
    )
    asset_servers: list[object] = []
    real_server = remotion_backend.InvocationAssetServer

    class TrackedAssetServer(real_server):
        def __init__(self, staging_dir: str | Path, *, allowed_origin: str) -> None:
            super().__init__(staging_dir, allowed_origin=allowed_origin)
            asset_servers.append(self)

    monkeypatch.setattr(remotion_backend, "InvocationAssetServer", TrackedAssetServer)
    before_threads = {
        thread.ident
        for thread in threading.enumerate()
        if thread.name.startswith("astrid-asset-server-")
    }

    render_error: BaseException | None = None
    result: RenderResult | None = None
    try:
        result = remotion_backend._protocol_render(
            request.for_backend(candidate.id),
            workspace=tmp_path,
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        render_error = exc
    finally:
        assert not list(tmp_path.glob(".remotion-empty-assets-*"))
        assert not list((tmp_path / "outputs").glob(".*.remotion-*"))
        assert not (tmp_path / "outputs" / ".remotion-props.json").exists()
        after_threads = {
            thread.ident
            for thread in threading.enumerate()
            if thread.name.startswith("astrid-asset-server-")
        }
        assert after_threads == before_threads
        for server in asset_servers:
            assert server.port == 0
            assert server.thread is None or not server.thread.is_alive()
            assert not server.staging_dir.exists()

    if render_error is not None:
        message = str(render_error)
        environment_failures = (
            "Failed to launch the browser process",
            "MachPortRendezvous",
            "Permission denied (1100)",
        )
        if any(reason in message for reason in environment_failures):
            pytest.skip(
                "Remotion backend smoke skipped: local browser/runtime is unavailable: "
                + message.splitlines()[-1]
            )
        raise render_error

    assert isinstance(result, RenderResult)
    video_path = tmp_path / result.video.path
    assert video_path.is_file()
    assert video_path.stat().st_size > 0
    assert result.backend_fragments["rendering.remotion"]["renderer"] == "remotion"
