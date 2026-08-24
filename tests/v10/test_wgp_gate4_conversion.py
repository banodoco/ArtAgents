"""Gate ④ — conversion fixtures byte-identical (Batch B7).

Golden fixtures pin the full conversion contract: whitelist drop,
declarative preset defaulting, explicit-model precedence, t2i
``video_length=1`` forcing, legacy key mapping. Any semantic change to
conversion changes bytes → mechanical rejection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.wgp_conversion import (
    PARAM_WHITELIST,
    TASK_TYPE_TO_MODEL,
    ConversionRefused,
    convert_task,
)
from astrid.core.integrations.reigh.wgp_gates import gate4_conversion_fixtures

FIXTURES = Path(__file__).parent / "fixtures" / "wgp_conversion"


def test_gate4_all_golden_fixtures_replay_byte_identical() -> None:
    report = gate4_conversion_fixtures(FIXTURES)
    assert report.ok, [
        (leg.name, leg.detail) for leg in report.legs if leg.status == "failed"
    ]
    fixture_cases = {p.name for p in FIXTURES.glob("*.json")}
    checked = {
        leg.name for leg in report.legs if leg.name.endswith(".json")
    }
    assert checked == fixture_cases


def test_t2i_forces_video_length_one_and_drops_off_whitelist_params() -> None:
    task = convert_task(
        {
            "prompt": "a cat",
            "resolution": "832x480",
            "video_length": 99,
            "model_name": "not-in-whitelist",
        },
        task_id="t1",
        task_type="wan_2_2_t2i",
    )
    assert task.model == "t2v_2_2"
    assert task.parameters["video_length"] == 1
    assert "model_name" not in task.parameters


def test_explicit_model_param_wins_over_the_declared_preset() -> None:
    task = convert_task(
        {"model": "i2v_2_2"}, task_id="t2", task_type="wan_2_2_i2v"
    )
    assert task.model == "i2v_2_2"


def test_unknown_task_type_refuses_typed_not_guessed() -> None:
    with pytest.raises(ConversionRefused, match="no TASK_TYPE_TO_MODEL preset"):
        convert_task({"prompt": "x"}, task_id="t3", task_type="mystery_type")


def test_orchestrator_rows_have_no_direct_preset_by_design() -> None:
    # Orchestrators coordinate children; they never generate directly.
    assert "travel_orchestrator" not in TASK_TYPE_TO_MODEL
    assert "join_clips_orchestrator" not in TASK_TYPE_TO_MODEL
    assert "edit_video_orchestrator" not in TASK_TYPE_TO_MODEL


def test_whitelist_covers_every_doc_03_param() -> None:
    for name in (
        "prompt",
        "model",
        "resolution",
        "video_length",
        "num_inference_steps",
        "guidance_scale",
        "seed",
        "negative_prompt",
        "image_url",
        "mask_url",
        "video_guide",
        "video_mask",
        "image_start",
        "image_end",
        "image_refs",
        "audio_guide",
        "activated_loras",
        "loras",
        "additional_loras",
        "phase_config",
    ):
        assert name in PARAM_WHITELIST


def test_url_backed_lora_download_refuses_until_setup_journal_exists() -> None:
    from astrid.core.integrations.reigh.wgp_conversion import ConversionRefused
    from astrid.core.integrations.reigh.wgp_conversion import download_loras

    calls: list[tuple[str, Path]] = []
    download_loras(
        {"additional_loras": ["cached_name"]},
        Path("/tmp") / "unused",
        downloader=lambda url, target: calls.append((url, target)),  # type: ignore[arg-type]
    )
    assert calls == []  # plain cache names never hit a downloader
    with pytest.raises(ConversionRefused, match="setup journal"):
        # Default downloader: URL fetch belongs to the B8 setup journal.
        download_loras(
            {"loras": ["https://example.com/x.safetensors"]},
            Path("/tmp") / "unused2",
        )


def test_fixture_bytes_are_stable_across_canonicalization() -> None:
    """The golden files themselves are canonical JSON (sorted, tight)."""
    for path in FIXTURES.glob("*.json"):
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        canonical = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
        assert raw == canonical, f"{path.name} is not canonical JSON"
