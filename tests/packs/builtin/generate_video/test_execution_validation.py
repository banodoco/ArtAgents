"""Execution validation tests for generation.generate_video."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from astrid.contracts.errors import AstridError
from astrid.core.executor.schema import load_executor_manifest
from astrid.core.model_catalog.schema import ModeSpec


_EXECUTOR_YAML = (
    Path(__file__).resolve().parents[4]
    / "astrid/packs/generation/executors/generate_video/executor.yaml"
)


def _assert_astrid_error(call, *cause_parts: str) -> AstridError:
    with pytest.raises(AstridError) as raised:
        call()
    error = raised.value
    for part in cause_parts:
        assert part in error.cause
    return error


def test_manifest_loads() -> None:
    manifest = load_executor_manifest(str(_EXECUTOR_YAML))
    assert manifest.id == "generation.generate_video"
    assert manifest.kind == "built_in"
    assert manifest.version == "2.0"


def test_execution_invalid_value(tmp_path: Path) -> None:
    """Invalid --execution is rejected after model/mode lookup."""
    from astrid.packs.generation.executors.generate_video.run import main

    out = tmp_path / "out"
    _assert_astrid_error(
        lambda: main(
            [
                "--model", "wan-2.2",
                "--mode", "t2v",
                "--execution", "both",
                "--prompt", "x",
                "--out", str(out),
            ]
        ),
        "model 'wan-2.2' mode 't2v' has no 'both' backend",
    )


def test_execution_invalid_value_lists_pair_specific_backends(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The error reports backends for the selected (model, mode) only."""
    from astrid.packs.generation.executors.generate_video.run import main

    out = tmp_path / "out"
    error = _assert_astrid_error(
        lambda: main(
            [
                "--model", "wan-2.2",
                "--mode", "t2v",
                "--execution", "local",
                "--prompt", "x",
                "--out", str(out),
            ]
        ),
        "model 'wan-2.2' mode 't2v' has no 'local' backend",
    )
    assert error.valid_options == ("cloud",)


def test_registry_lookup_failure_is_reported_as_cli_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing backend descriptors become CLI errors instead of raw exceptions."""
    from astrid.packs.generation.executors.generate_video import run as run_mod
    from astrid.core.generation.backends.registry import GenerationBackendRegistry

    class EmptyBackendRegistry(GenerationBackendRegistry):
        def __init__(self) -> None:
            self._descriptors = {}

    monkeypatch.setattr(
        run_mod,
        "load_default_generation_backend_registry",
        lambda: EmptyBackendRegistry(),
    )

    out = tmp_path / "out"
    _assert_astrid_error(
        lambda: run_mod.main(
            [
                "--model", "wan-2.2",
                "--mode", "t2v",
                "--execution", "cloud",
                "--prompt", "x",
                "--out", str(out),
            ]
        ),
        "generation backend 'cloud' is not registered",
    )


def test_video_prompt_file_custom_features_survive_helper_validation() -> None:
    """Video helper validation keeps declared custom features and drops extras."""
    from astrid.packs.generation.executors.generate_video.run import (
        _build_requested_params,
        _check_required,
        _drop_unsupported,
    )

    args = argparse.Namespace(
        prompt=None,
        negative_prompt=None,
        seed=None,
        count=1,
        resolution=None,
        image_ref=None,
        image_end_ref=None,
        frames=None,
        fps=None,
        duration=None,
        guidance_scale=None,
        steps=None,
        shift=None,
        loras=None,
        enable_safety_checker=None,
        enable_prompt_expansion=None,
        acceleration=None,
    )
    mode_spec = ModeSpec(
        supports=("prompt", "image_ref", "story_ref"),
        requires=("prompt", "image_ref", "story_ref"),
        backends={},
    )

    requested = _build_requested_params(
        args,
        prompt_text="row prompt",
        prompt_entry={
            "prompt": "row prompt",
            "image_ref": "first.png",
            "story_ref": "story.json",
            "rogue_feature": "ignore-me",
        },
    )
    _check_required(mode_spec, "i2v", "custom-video", requested)
    filtered, warnings, dropped = _drop_unsupported(
        mode_spec,
        "i2v",
        "custom-video",
        requested,
    )

    assert filtered["image_ref"] == "first.png"
    assert filtered["story_ref"] == "story.json"
    assert "rogue_feature" not in filtered
    assert set(dropped) == {"count", "rogue_feature"}
    assert {warning["feature"] for warning in warnings} == {"count", "rogue_feature"}
