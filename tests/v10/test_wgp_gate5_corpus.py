"""Gate ⑤ — seeded output-shape corpus + semantic-diff remainder.

CPU-feasible deterministic shape assertions run mechanically over the
representative corpus; every real-generation semantic-diff leg is
recorded ``blocked(CUDA)`` carrying the phase stop-condition note —
documented, never silently dropped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.wgp_gates import (
    SEMANTIC_DIFF_STATUS,
    STOP_CONDITION_NOTE,
    cpu_shape_assertions,
    gate5_output_corpus,
)

CORPUS = Path(__file__).parent / "fixtures" / "wgp_corpus" / "corpus.json"


@pytest.fixture()
def corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def test_gate5_shape_assertions_green_and_semantic_legs_blocked() -> None:
    if not CORPUS.is_file():  # pragma: no cover
        pytest.skip(f"corpus missing at {CORPUS}")
    report = gate5_output_corpus(CORPUS)
    shape_legs = [leg for leg in report.legs if leg.name.startswith("shape:")]
    semantic_legs = [
        leg for leg in report.legs if leg.name.startswith("semantic_diff:")
    ]
    assert shape_legs and all(leg.status == "ok" for leg in shape_legs)
    assert semantic_legs and all(
        leg.status == "skipped" and leg.reason == STOP_CONDITION_NOTE
        and SEMANTIC_DIFF_STATUS in leg.detail
        for leg in semantic_legs
    ), "semantic legs must be recorded blocked(CUDA), never dropped"


def test_corpus_covers_representative_wgp_capabilities(corpus: dict) -> None:
    capabilities = {case["capability"] for case in corpus["cases"]}
    assert {"reigh.wan_2_2_t2i", "reigh.wan_2_2_i2v"} <= capabilities
    seeds = [case.get("seed") for case in corpus["cases"]]
    assert all(seed is not None for seed in seeds), "fixed-seed policy"


def test_shape_facts_follow_the_conversion_contract() -> None:
    from astrid.core.integrations.reigh.wgp_conversion import convert_task

    task = convert_task(
        {"prompt": "x", "resolution": "640x360", "video_length": 4},
        task_id="s1",
        task_type="wan_2_2_i2v",
    )
    assert cpu_shape_assertions(task) == {
        "frames": 4,
        "width": 640,
        "height": 360,
    }
    t2i = convert_task(
        {"prompt": "x", "resolution": "640x360"},
        task_id="s2",
        task_type="wan_2_2_t2i",
    )
    assert cpu_shape_assertions(t2i)["frames"] == 1
