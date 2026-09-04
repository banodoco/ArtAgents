from __future__ import annotations

import pytest

from astrid.packs.wan2gp.src.compiler import compile_from_inputs


def test_canonical_wan22_gets_native_abi_defaults_deterministically() -> None:
    inputs = {"prompt": "x", "model": "wan-2.2"}

    first = compile_from_inputs(inputs)
    second = compile_from_inputs(inputs)

    assert first["model_type"] == "vace_fun_14B_2_2"
    assert first["image_refs_strengths"] == []
    assert first == second


def test_explicit_native_abi_values_are_preserved() -> None:
    settings = compile_from_inputs(
        {"prompt": "x", "model_type": "custom", "image_refs_strengths": [0.5]}
    )

    assert settings["model_type"] == "custom"
    assert settings["image_refs_strengths"] == [0.5]


def test_missing_prompt_still_raises() -> None:
    with pytest.raises(ValueError, match="prompt is required"):
        compile_from_inputs({"model": "wan-2.2"})
