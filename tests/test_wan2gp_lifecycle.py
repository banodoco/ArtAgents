from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.packs.wan2gp.src.compiler import (
    compile_from_inputs,
    portable_digest,
    runner_fingerprint,
    warmth_identity,
)
from astrid.packs.wan2gp.src.driver import (
    CancellationPolicy,
    CancellationToken,
    FakePersistentRunner,
    PersistentRunnerState,
)


@pytest.fixture
def settings() -> dict[str, object]:
    return compile_from_inputs(
        {
            "prompt": "a paper kite over a quiet lake",
            "model": "wan-2.2",
            "resolution": "320x240",
            "frames": 3,
            "fps": 12,
            "seed": 17,
            "wan2gp_path": "/machine/checkout-a",
            "attempt_root": "/machine/attempt-a",
        }
    )


def test_cancellation_token_is_cooperative_and_idempotent() -> None:
    token = CancellationToken()
    assert token.cancelled is False
    assert token.cancel("fixture stop") is True
    assert token.cancel("ignored second stop") is False
    assert token.cancelled is True
    assert token.reason == "fixture stop"
    with pytest.raises(RuntimeError, match="fixture stop"):
        token.raise_if_cancelled()


def test_fake_cancellation_leaves_persistent_runner_warm(
    tmp_path: Path, settings: dict[str, object]
) -> None:
    state_path = tmp_path / "runner-state.jsonl"
    runner = FakePersistentRunner(state_path, output_root=tmp_path / "outputs")

    result = runner.run(
        settings,
        policy=CancellationPolicy(cancel_after_steps=1),
        work_steps=3,
    )

    assert result.status == "cancelled"
    assert result.cancelled is True
    assert result.generated_files == []
    assert result.runner_alive is True
    assert result.state.status == PersistentRunnerState.WARM
    events = [json.loads(line) for line in state_path.read_text().splitlines()]
    assert [event["event"] for event in events] == [
        "runner_created",
        "runner_started",
        "run_started",
        "run_cancelled",
    ]
    assert events[-1]["reason"] == "cancelled by policy at step 1"


def test_persistent_state_reopens_and_reuses_warm_identity(
    tmp_path: Path, settings: dict[str, object]
) -> None:
    state_path = tmp_path / "runner-state.jsonl"
    output_root = tmp_path / "outputs"
    first = FakePersistentRunner(state_path, output_root=output_root, runner_id="fixture-runner")
    first_result = first.run(settings, fixture={"fixture": "one"})
    assert first_result.status == "succeeded"
    assert first.is_alive() is True

    reopened_state = PersistentRunnerState.load(state_path)
    assert reopened_state.snapshot.status == PersistentRunnerState.WARM
    assert reopened_state.is_alive() is True
    second = FakePersistentRunner(
        state_path,
        output_root=output_root,
        runner_id="fixture-runner",
    )
    second_result = second.run(settings, output_name="second.json", fixture={"fixture": "two"})
    assert second_result.status == "succeeded"
    assert second_result.fingerprint == first_result.fingerprint
    assert second_result.warmth_identity == first_result.warmth_identity
    assert second_result.state.total_runs == 2
    assert second_result.state.successful_runs == 2
    assert second_result.state.status == PersistentRunnerState.WARM
    assert json.loads((output_root / "second.json").read_text()) == {"fixture": "two"}


def test_runner_and_warmth_identity_are_portable_and_deterministic(
    settings: dict[str, object],
) -> None:
    relocated = dict(settings)
    relocated.update(
        {
            "wan2gp_path": "/another/machine/checkout",
            "attempt_root": "/another/machine/attempt",
            "device": "cuda:7",
        }
    )
    assert portable_digest(settings) == portable_digest(relocated)
    assert runner_fingerprint(settings) == runner_fingerprint(relocated)
    assert warmth_identity(settings, warmth_profile="cpu-fake") == warmth_identity(
        relocated, warmth_profile="cpu-fake"
    )
    assert warmth_identity(settings, warmth_profile="cpu-fake") != warmth_identity(
        settings, warmth_profile="cpu-fake-v2"
    )
    assert runner_fingerprint(settings) == runner_fingerprint(settings)


def test_fake_output_containment_rejects_escape_without_writing_outside(
    tmp_path: Path, settings: dict[str, object]
) -> None:
    state_path = tmp_path / "runner-state.jsonl"
    output_root = tmp_path / "outputs"
    runner = FakePersistentRunner(state_path, output_root=output_root)

    result = runner.run(settings, escape_output=True)

    escaped = tmp_path / "escaped-fake-output.json"
    assert result.status == "failed"
    assert result.containment_ok is False
    assert result.generated_files == []
    assert "output containment violated" in result.errors[0]
    assert escaped.exists() is False
    assert result.runner_alive is True
    assert runner.state.snapshot.failed_runs == 1


def test_one_shot_cancellation_is_structured_before_engine_lookup(
    tmp_path: Path, settings: dict[str, object]
) -> None:
    from astrid.packs.wan2gp.src.driver import one_shot_run

    result = one_shot_run(
        settings=settings,
        attempt_root=tmp_path / "attempt",
        wan2gp_root=tmp_path / "missing-engine",
        cancelled=lambda: True,
    )
    assert result.success is False
    assert result.errors == ["cancelled: cancelled"]
    assert result.spool == (tmp_path / "attempt" / "outputs").resolve()
