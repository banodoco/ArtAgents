from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from astrid.core.generation.backends import GenerationResult
from astrid.core.generation.backends.codex import CodexBackend
from astrid.core.model_catalog.registry import ModelRegistry


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
    b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


SESSION_ID = "11111111-1111-1111-1111-111111111111"


def _image_entry():
    return ModelRegistry.load_default().get_by_mode("flux-dev", "t2i")


def test_codex_backend_copies_fresh_png_and_attaches_reference(
    tmp_path: Path,
) -> None:
    entry, _mode_spec = _image_entry()
    generated_root = tmp_path / "generated_images"
    session_dir = generated_root / SESSION_ID
    session_dir.mkdir(parents=True)
    reference = tmp_path / "reference.png"
    reference.write_bytes(PNG_BYTES)
    seen: dict[str, object] = {}

    def fake_runner(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        (session_dir / "ig_result.png").write_bytes(PNG_BYTES)
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=f"session id: {SESSION_ID}\nGENERATED\n",
        )

    backend = CodexBackend(runner=fake_runner, generated_images_dir=generated_root)
    out_dir = tmp_path / "out"

    result = backend.generate(
        entry=entry,
        mode="t2i",
        params={
            "prompt": "a red bicycle",
            "seed": 7,
            "size": "1024x1024",
            "quality": "low",
            "background": "transparent",
            "image_ref": str(reference),
            "timeout": 12,
        },
        out_dir=out_dir,
    )

    assert result.ok is True
    assert result.image_paths == [out_dir.resolve() / "codex_000.png"]
    assert result.image_paths[0].read_bytes() == PNG_BYTES
    assert result.model_actual == "codex/gpt-image"
    assert result.request_id == SESSION_ID
    assert result.source_urls == [str(session_dir / "ig_result.png")]
    cmd = seen["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0:2] == ["codex", "exec"]
    assert any(part == f"--image={reference}" for part in cmd)
    assert seen["kwargs"]["timeout"] == 12  # type: ignore[index]
    assert seen["kwargs"]["stdin"] is subprocess.DEVNULL  # type: ignore[index]


def test_codex_backend_fails_loud_when_session_has_no_png(tmp_path: Path) -> None:
    entry, _mode_spec = _image_entry()
    generated_root = tmp_path / "generated_images"
    (generated_root / SESSION_ID).mkdir(parents=True)

    def fake_runner(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=f"session id: {SESSION_ID}\nGENERATED\n",
        )

    backend = CodexBackend(runner=fake_runner, generated_images_dir=generated_root)

    with pytest.raises(RuntimeError, match="produced no ig_\\*.png"):
        backend.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "a red bicycle"},
            out_dir=tmp_path / "out",
        )


def test_generate_image_codex_preflight_falls_back_to_cloud(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from astrid.packs.generation.executors.generate_image import run as run_mod

    class FakeAdapter:
        def generate(self, *, entry, mode: str, params: dict[str, object], out_dir: Path):
            image_path = out_dir / "cloud_result.png"
            image_path.write_bytes(PNG_BYTES)
            assert mode == "t2i"
            assert params["prompt"] == "fallback test"
            return GenerationResult(
                image_paths=[image_path],
                seed_used=int(params["seed"]),
                model_actual="fal-ai/flux/dev",
                applied_features=["prompt", "seed"],
                request_id="fal-req",
            )

    class FakeRegistry:
        def create(self, execution: str, *, env_file: Path | None) -> FakeAdapter:
            assert execution == "cloud"
            return FakeAdapter()

    monkeypatch.setattr(
        run_mod,
        "load_default_generation_backend_registry",
        lambda: FakeRegistry(),
    )
    monkeypatch.setattr(
        run_mod,
        "codex_unavailable_reason",
        lambda: "`codex` binary not found on PATH",
    )
    monkeypatch.setattr(run_mod, "embed_png_text", lambda path, fields: None)

    out = tmp_path / "out"
    result = run_mod.generate_core(
        [
            "--model",
            "flux-dev",
            "--mode",
            "t2i",
            "--execution",
            "codex",
            "--prompt",
            "fallback test",
            "--out",
            str(out),
            "--seed",
            "9",
        ]
    )

    captured = capsys.readouterr()
    assert "falling back to cloud backend" in captured.err
    assert result.model_actual == "fal-ai/flux/dev"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["execution"] == "cloud"
    assert manifest["warnings"][0]["feature"] == "codex"
    assert "not found on PATH" in manifest["warnings"][0]["reason"]
