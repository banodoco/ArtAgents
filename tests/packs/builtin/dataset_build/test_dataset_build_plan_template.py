from __future__ import annotations

from pathlib import Path

from astrid.core.task.plan import load_plan
from astrid.packs.training.orchestrators.dataset_build.plan_template import (
    build_plan_v2,
    emit_plan_json,
)


def test_dataset_build_plan_template_emits_single_opaque_local_stage(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    run_root = tmp_path / "run"

    plan = build_plan_v2(
        python_exec="python3",
        run_root=run_root,
        config=config,
        run_id="fixture-run",
    )

    assert plan["version"] == 2
    assert plan["plan_id"] == "dataset-build-fixture-run"
    steps = plan["steps"]
    assert len(steps) == 1
    step = steps[0]
    assert step["id"] == "dataset-build"
    assert step["adapter"] == "local"
    assert "--config" in step["command"]
    assert str(config.resolve()) in step["command"]
    assert "--out" in step["command"]
    assert str(run_root.resolve()) in step["command"]
    produces = step["produces"]
    assert list(produces) == ["review_state"]
    assert produces["review_state"]["path"] == str(
        (run_root / "review_state.json").resolve()
    )


def test_dataset_build_plan_template_preserves_resume_affecting_flags() -> None:
    plan = build_plan_v2(
        python_exec="python3",
        run_root="run-dir",
        config="config.yaml",
        review_decisions="decisions.json",
        skip_review=True,
        review_only=True,
        run_id="fixture-run",
    )

    command = plan["steps"][0]["command"]
    assert "--review-decisions" in command
    assert "decisions.json" in command
    assert "--skip-review" in command
    assert "--review-only" in command


def test_dataset_build_plan_template_round_trips_through_task_kernel(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    plan = build_plan_v2(
        python_exec="python3",
        run_root=tmp_path / "run",
        config=config,
        run_id="fixture-run",
    )

    plan_path = tmp_path / "plan.json"
    emit_plan_json(plan, plan_path)
    loaded = load_plan(plan_path)

    assert loaded.version == 2
    assert len(loaded.steps) == 1
    assert loaded.steps[0].id == "dataset-build"
