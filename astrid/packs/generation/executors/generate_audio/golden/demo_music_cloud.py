#!/usr/bin/env python3
"""Golden demo: cloud music generation via generate_audio.

Covers the wired cloud music models:

  - stable-audio-3-medium / music / cloud
  - minimax-music-v2.6 / music / cloud
  - ace-step / music / cloud

Uses mocked ``fal_submit_and_poll`` and ``HttpClient.get_bytes`` so no external
services or API keys are required.  Every cell exercises the full executor
pipeline (``generate_audio.run.main``) and asserts manifest shape correctness.

Usage::

    python -m astrid.packs.generation.executors.generate_audio.golden.demo_music_cloud
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

# Bypass the canonical-entrypoint guard so this demo can import run.py directly.
os.environ.setdefault("ASTRID_INTERNAL_INVOCATION", "1")


# ---------------------------------------------------------------------------
# Minimal valid MP3 bytes — enough for the executor to compute a content hash.
# ---------------------------------------------------------------------------

_MINIMAL_MP3 = (
    b"\xff\xfb\x90\x00"  # MPEG-1 Layer III frame sync + header
    + b"\x00" * 417      # placeholder frame payload
)


def _minimal_mp3_bytes() -> bytes:
    """Return a minimal MP3 file."""
    return _MINIMAL_MP3


# ---------------------------------------------------------------------------
# Mock fal result helpers
# ---------------------------------------------------------------------------

def _make_fal_result(url: str = "https://mock.fal.run/output.mp3") -> dict[str, Any]:
    return {
        "audio": {"url": url},
        "request_id": "mock-req-audio-0001",
        "cost": 0.05,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_executor(
    model: str,
    mode: str,
    execution: str,
    prompt: str,
    *,
    seed: int | None = None,
    duration: float | None = None,
    lyrics_prompt: str | None = None,
    instrumental: str | None = None,
    output_format: str | None = None,
) -> Path:
    """Run the audio executor with mocked fal transport and return run_dir."""
    from astrid.core.generation.backends import fal as fal_mod
    from astrid.packs.generation.executors.generate_audio import run

    tmpdir = tempfile.mkdtemp()
    out = Path(tmpdir) / "out"
    argv = [
        "--model", model,
        "--mode", mode,
        "--execution", execution,
        "--prompt", prompt,
        "--out", str(out),
    ]
    if seed is not None:
        argv.extend(["--seed", str(seed)])
    if duration is not None:
        argv.extend(["--duration", str(duration)])
    if lyrics_prompt is not None:
        argv.extend(["--lyrics-prompt", lyrics_prompt])
    if instrumental is not None:
        argv.extend(["--instrumental", instrumental])
    if output_format is not None:
        argv.extend(["--output-format", output_format])

    with patch.object(fal_mod, "fal_submit_and_poll", return_value=_make_fal_result()):
        with patch.object(fal_mod.FalBackend, "_resolve_api_key", return_value="mock-key"):
            # The backend lazily creates its client; patch the class so the
            # instance uses a client whose get_bytes returns fake audio.
            real_init = fal_mod.FalBackend.__init__

            def patched_init(self, env_file=None, client=None):
                real_init(self, env_file=env_file, client=client)
                # Ensure downloads succeed
                self._client.get_bytes = lambda url, timeout=120: _minimal_mp3_bytes()

            with patch.object(fal_mod.FalBackend, "__init__", patched_init):
                run.main(argv)

    return out.resolve()


def _assert_manifest(run_dir: Path, model: str, mode: str) -> None:
    """Assert that the generated manifest has the expected audio shape."""
    manifest_path = run_dir / "manifest.json"
    assert manifest_path.exists(), f"manifest not found at {manifest_path}"
    manifest = json.loads(manifest_path.read_text())

    assert manifest["kind"] == "generation.generate_audio"
    assert manifest["modality"] == "audio"
    assert manifest["mode_used"] == mode
    assert manifest["model"] == model
    assert manifest["execution"] == "cloud"
    assert manifest["inputs"]["model"] == model
    assert manifest["inputs"]["mode"] == mode

    assert manifest["outputs"], "manifest must contain outputs"
    for output in manifest["outputs"]:
        assert output["path"].startswith("audio/")
        assert output["content_hash"].startswith("sha256:")
        assert output["bytes"] > 0
        assert "duration_seconds" in output

    print(f"  OK: {model}/{mode} -> {manifest_path}")


# ---------------------------------------------------------------------------
# Demo cases
# ---------------------------------------------------------------------------

def demo_stable_audio_3_medium() -> None:
    print("demo: stable-audio-3-medium / music / cloud")
    run_dir = _call_executor(
        model="stable-audio-3-medium",
        mode="music",
        execution="cloud",
        prompt="a serene ambient drone",
        seed=42,
        duration=10.0,
        output_format="mp3",
    )
    _assert_manifest(run_dir, "stable-audio-3-medium", "music")


def demo_minimax_music() -> None:
    print("demo: minimax-music-v2.6 / music / cloud")
    run_dir = _call_executor(
        model="minimax-music-v2.6",
        mode="music",
        execution="cloud",
        prompt="upbeat synth-pop chorus",
        seed=42,
        duration=10.0,
        instrumental="true",
    )
    _assert_manifest(run_dir, "minimax-music-v2.6", "music")


def demo_ace_step() -> None:
    print("demo: ace-step / music / cloud")
    run_dir = _call_executor(
        model="ace-step",
        mode="music",
        execution="cloud",
        prompt="lo-fi hip hop beat",
        seed=42,
        duration=30.0,
    )
    _assert_manifest(run_dir, "ace-step", "music")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    print("Running generate_audio cloud music golden demo...")
    demo_stable_audio_3_medium()
    demo_minimax_music()
    demo_ace_step()
    print("All cloud music cells passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
