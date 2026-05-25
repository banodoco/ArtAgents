from __future__ import annotations

import inspect
import json
from pathlib import Path

from astrid.core.adapter import RunContext
from astrid.core.adapter.local import LocalAdapter
from astrid.core.adapter.manual import ManualAdapter
from astrid.core.task.plan import Step


def _ctx(tmp_path: Path, *, step_version: int = 1) -> RunContext:
    project_root = tmp_path / "projects" / "demo"
    project_root.mkdir(parents=True, exist_ok=True)
    return RunContext(
        slug="demo",
        run_id="run-1",
        project_root=project_root,
        plan_step_path=("s1",),
        step_version=step_version,
    )


def _step_dir(ctx: RunContext) -> Path:
    return (
        ctx.project_root
        / "runs"
        / ctx.run_id
        / "steps"
        / "s1"
        / f"v{ctx.step_version}"
    )


def test_local_complete_fails_closed_when_returncode_missing_even_without_produces(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path)
    _step_dir(ctx).mkdir(parents=True)
    step = Step(id="s1", adapter="local", command="echo ok")

    result = LocalAdapter().complete(step, ctx)

    assert result.status == "failed"
    assert "returncode" in (result.reason or "")


def test_local_complete_fails_closed_when_returncode_is_not_an_int(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path)
    step_dir = _step_dir(ctx)
    step_dir.mkdir(parents=True)
    (step_dir / "returncode").write_text("not-an-int", encoding="utf-8")
    step = Step(id="s1", adapter="local", command="echo ok")

    result = LocalAdapter().complete(step, ctx)

    assert result.status == "failed"
    assert "returncode" in (result.reason or "")


def test_manual_completion_missing_status_fails_closed(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    produces = _step_dir(ctx) / "produces"
    produces.mkdir(parents=True)
    (produces / "completion.json").write_text(
        json.dumps({"source": "ack"}),
        encoding="utf-8",
    )
    step = Step(id="s1", adapter="manual", command="manual-review")

    result = ManualAdapter().complete(step, ctx)

    assert result.status == "failed"
    assert "status" in (result.reason or "")


def test_manual_completion_unknown_status_fails_closed(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    produces = _step_dir(ctx) / "produces"
    produces.mkdir(parents=True)
    (produces / "completion.json").write_text(
        json.dumps({"source": "ack", "status": "maybe"}),
        encoding="utf-8",
    )
    step = Step(id="s1", adapter="manual", command="manual-review")

    result = ManualAdapter().complete(step, ctx)

    assert result.status == "failed"
    assert "status" in (result.reason or "")


def test_local_and_manual_dispatch_sidecars_use_atomic_helper() -> None:
    local_source = inspect.getsource(LocalAdapter.dispatch)
    manual_source = inspect.getsource(ManualAdapter.dispatch)

    assert "write_json_sidecar" in local_source
    assert "write_json_sidecar" in manual_source
    assert ".write_text(" not in local_source
    assert ".write_text(" not in manual_source
