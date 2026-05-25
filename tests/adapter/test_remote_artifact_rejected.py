"""Remote-artifact adapter active rejection paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.adapter import RunContext
from astrid.core.adapter.remote_artifact import RemoteArtifactAdapter
from astrid.core.task.plan import Step


@pytest.fixture
def adapter() -> RemoteArtifactAdapter:
    return RemoteArtifactAdapter()


def _make_ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        slug="demo",
        run_id="run-1",
        project_root=tmp_path,
        plan_step_path=("s1",),
        step_version=1,
    )


def test_dispatch_rejects_empty_command(adapter: RemoteArtifactAdapter, tmp_path: Path) -> None:
    result = adapter.dispatch(Step(id="s1", adapter="remote-artifact", command=""), _make_ctx(tmp_path))
    assert result.status == "rejected"
    assert "non-empty command" in (result.reason or "")


def test_dispatch_rejects_unparseable_command(adapter: RemoteArtifactAdapter, tmp_path: Path) -> None:
    result = adapter.dispatch(
        Step(id="s1", adapter="remote-artifact", command="python -c 'unterminated"),
        _make_ctx(tmp_path),
    )
    assert result.status == "rejected"
    assert "shell-parseable" in (result.reason or "")


def test_poll_failed_on_corrupt_remote_state(adapter: RemoteArtifactAdapter, tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    step_dir = tmp_path / "runs" / "run-1" / "steps" / "s1" / "v1"
    step_dir.mkdir(parents=True)
    (step_dir / "remote_state.json").write_text("{bad", encoding="utf-8")
    result = adapter.poll(Step(id="s1", adapter="remote-artifact", command="echo ok"), ctx)
    assert result.status == "failed"

