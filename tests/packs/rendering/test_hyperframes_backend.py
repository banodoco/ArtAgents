"""HyperFrames third-party backend — end-to-end proof of the pluggable
renderer contract.

Locks the epic's core promise: a trusted pack can add a timeline render
backend (here: heygen-com/hyperframes, HTML→MP4) without editing core.
The pack lives at ``tests/fixtures/renderer_packs/hyperframes`` and is
discovered via an extra pack root.  The test exercises:

* discovery + inspect through the registry/CLI surface;
* honest support (text-only accepted; media/fade timelines rejected);
* a real render through the public service (Node 22+ and FFmpeg required);
* the artifact probe/validation and provenance sidecar.

The real-render case SKIPS when node/ffmpeg are absent or the pinned
hyperframes CLI cannot be installed (network), so CI stays honest without
pretending to render.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

from astrid.core.rendering.registry import load_default_registries
from astrid.sdk.rendering import render, support

ROOT = Path(__file__).resolve().parents[3]
PACK_ROOT = ROOT / "tests" / "fixtures" / "renderer_packs"
HYPERFRAMES_ROOT = PACK_ROOT / "hyperframes"
HYPERFRAMES_ID = "hyperframes.renderer"
NODE = shutil.which("node")


def _require_hyperframes_environment() -> str:
    """Return a node >= 22 executable, or skip.

    Prefers a system/nvm node that satisfies HyperFrames' Node 22+
    requirement (v20 on PATH is common; a newer nvm node usually exists).
    """
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is unavailable")
    candidates: list[str] = []
    if NODE is not None:
        candidates.append(NODE)
    nvm_versions = Path.home() / ".nvm" / "versions" / "node"
    if nvm_versions.is_dir():
        candidates.extend(
            str(path / "bin" / "node")
            for path in sorted(nvm_versions.iterdir(), reverse=True)
            if (path / "bin" / "node").is_file()
        )
    for node in candidates:
        version = subprocess.run(
            [node, "--version"], capture_output=True, text=True, check=False
        ).stdout.strip()
        try:
            major = int(version.lstrip("v").split(".")[0])
        except (ValueError, IndexError):
            continue
        if major >= 22:
            return node
    pytest.skip("node >= 22 required for hyperframes (checked system + nvm)")


@contextmanager
def _node_on_path(node: str):
    """Prepend *node*'s bin dir to PATH so `npx` resolves the same node."""
    bin_dir = str(Path(node).resolve().parent)
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{old_path}"
    try:
        yield
    finally:
        os.environ["PATH"] = old_path


def _text_timeline(tmp_path: Path) -> Path:
    payload = {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {
                "canvas": {"width": 640, "height": 360, "fps": 24},
                "background": "#1a1a2e",
            }
        },
        "tracks": [
            {"id": "v1", "kind": "visual", "label": "Title"},
            {"id": "v2", "kind": "visual", "label": "Subtitle"},
        ],
        "clips": [
            {
                "id": "title",
                "at": 0.0,
                "track": "v1",
                "clipType": "text",
                "hold": 1.5,
                "params": {"content": "Hello HyperFrames", "fontSize": 64, "color": "#ffffff", "weight": 700},
            },
            {
                "id": "sub",
                "at": 1.0,
                "track": "v2",
                "clipType": "text",
                "hold": 1.0,
                "params": {"content": "rendered by Astrid", "fontSize": 28, "color": "#a0e0ff"},
            },
        ],
    }
    path = tmp_path / "timeline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_hyperframes_pack_is_discovered_and_inspected() -> None:
    renderers, _planners, _finalizers = load_default_registries(
        extra_pack_roots=(str(PACK_ROOT),),
        include_installed=True,
    )
    candidates = renderers.candidates(HYPERFRAMES_ID)
    assert len(candidates) == 1, [c.to_dict() for c in candidates]
    candidate = candidates[0]
    assert candidate.id == HYPERFRAMES_ID
    assert candidate.source_kind == "extra"
    assert candidate.manifest.command == ("python3", "render.py")
    assert "node" in candidate.manifest.required_binaries
    assert candidate.execution_eligible is True


def test_hyperframes_support_is_honest(tmp_path: Path) -> None:
    text = _text_timeline(tmp_path)
    report = support(
        HYPERFRAMES_ID,
        timeline_path=text,
        extra_pack_roots=(str(PACK_ROOT),),
    )
    assert report.supported is True

    media = tmp_path / "media.json"
    media.write_text(
        json.dumps(
            {
                "theme_overrides": {"visual": {"canvas": {"width": 640, "height": 360, "fps": 24}}},
                "tracks": [{"id": "v", "kind": "visual"}],
                "clips": [{"id": "m", "at": 0, "track": "v", "clipType": "media", "asset": "x"}],
            }
        ),
        encoding="utf-8",
    )
    report = support(HYPERFRAMES_ID, timeline_path=media, extra_pack_roots=(str(PACK_ROOT),))
    assert report.supported is False
    assert any("media" in reason for reason in report.reasons)

    fade = tmp_path / "fade.json"
    fade.write_text(
        json.dumps(
            {
                "theme_overrides": {"visual": {"canvas": {"width": 640, "height": 360, "fps": 24}}},
                "tracks": [{"id": "v", "kind": "visual"}],
                "clips": [{"id": "t", "at": 0, "track": "v", "clipType": "text", "hold": 1, "params": {"content": "x", "fadeIn": 0.3}}],
            }
        ),
        encoding="utf-8",
    )
    report = support(HYPERFRAMES_ID, timeline_path=fade, extra_pack_roots=(str(PACK_ROOT),))
    assert report.supported is False
    assert any("fadeIn" in reason for reason in report.reasons)


@pytest.mark.timeout(600)
def test_hyperframes_real_render_through_public_service(tmp_path: Path) -> None:
    node = _require_hyperframes_environment()
    timeline = _text_timeline(tmp_path)
    output = tmp_path / "hyperframes.mp4"
    try:
        with _node_on_path(node):
            published = render(
                timeline_path=timeline,
                assets_registry_path=None,
                out_path=output,
                backend=HYPERFRAMES_ID,
                extra_pack_roots=(str(PACK_ROOT),),
            )
    except Exception as exc:  # noqa: BLE001 - network/CLI availability
        message = str(exc)
        if "npx" in message or "ENOTFOUND" in message or "network" in message:
            pytest.skip(f"hyperframes CLI unavailable: {message[:120]}")
        raise

    assert Path(published).is_file()
    assert Path(published).stat().st_size > 0
    sidecar = Path(f"{published}.provenance.json")
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["engine"] == HYPERFRAMES_ID
    assert payload["routing"]["resolved_backend"] == HYPERFRAMES_ID
    assert payload["audio_ownership"] == "none"
    assert payload["backend_fragments"][HYPERFRAMES_ID]["renderer"] == "hyperframes"
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,width,height",
            "-of",
            "csv",
            str(published),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "h264" in probe
    assert "640" in probe and "360" in probe
