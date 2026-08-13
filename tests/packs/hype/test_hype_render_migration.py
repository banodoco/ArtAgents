from __future__ import annotations

import argparse
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.contracts.run_status import RunStatus
from astrid.core.project.project import create_project
from astrid.core.project.run import write_run_record
from astrid.core.rendering import attached
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV
from astrid.packs.video_editing.orchestrators.hype import steps


class _Registry:
    def __init__(self, resolved_id: str = "rendering.render") -> None:
        self.resolved_id = resolved_id

    def get(self, executor_id: str) -> SimpleNamespace:
        assert executor_id == "rendering.render"
        return SimpleNamespace(id=self.resolved_id)


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "brief_out": tmp_path / "brief",
        "python_exec": "/opt/python",
        "theme": tmp_path / "theme.json",
        "extra_args": {},
        "editor_iteration": 1,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_hype_render_step_uses_qualified_facade_and_declares_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _args(tmp_path)
    render_step = next(step for step in steps.build_pool_steps() if step.name == "render")

    assert render_step.sentinels == ("hype.mp4", "hype.mp4.provenance.json")
    assert render_step.build_cmd(args) == [
        "/opt/python",
        "-m",
        "astrid",
        "executors",
        "run",
        "rendering.render",
        "--out",
        str(args.brief_out),
        "--input",
        f"timeline={args.brief_out / 'hype.timeline.json'}",
        "--input",
        f"assets_registry={args.brief_out / 'hype.assets.json'}",
        "--input",
        f"theme={args.theme}",
    ]
    assert "astrid.packs.rendering" not in " ".join(render_step.build_cmd(args))

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        steps,
        "invoke_attached_render",
        lambda *_args, **kwargs: calls.append(kwargs) or args.brief_out / "hype.mp4",
    )
    steps.invoke_hype_render(args)
    assert calls[0]["backend_config"] == {
        "rendering.remotion": {"theme_path": str(args.theme)},
        "rendering.legacy_hybrid": {"theme_path": str(args.theme)},
    }


def test_hype_attached_render_writes_default_pair_and_only_parent_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    create_project("demo", root=projects_root)
    write_run_record(
        "demo",
        "hype-parent",
        root=projects_root,
        tool_id="video_editing.hype",
        kind="orchestrator",
        status=RunStatus.RUNNING,
    )
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    for name in (TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV):
        monkeypatch.delenv(name, raising=False)

    calls: list[object] = []

    def fake_run(request, registry):
        resolved = registry.get(request.executor_id)
        calls.append((request, resolved))
        output = Path(request.out) / request.inputs["output_name"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(resolved.id, encoding="utf-8")
        sidecar = Path(f"{output}.provenance.json")
        sidecar.write_text('{"renderer":"fixture"}\n', encoding="utf-8")
        return SimpleNamespace(
            ok=True,
            error=None,
            outputs={"video": str(output), "provenance": str(sidecar)},
        )

    monkeypatch.setattr(attached, "run_executor", fake_run)
    monkeypatch.setattr(
        attached,
        "load_default_registry",
        lambda **_kwargs: _Registry("local.hype-render"),
    )
    args = _args(
        tmp_path,
        project="demo",
        render_parent_run_id="hype-parent",
        theme=None,
    )

    result = steps.invoke_hype_render(args)

    assert result == (args.brief_out / "hype.mp4").resolve()
    assert result.read_text(encoding="utf-8") == "local.hype-render"
    assert Path(f"{result}.provenance.json").is_file()
    request = calls[0][0]
    assert request.executor_id == "rendering.render"
    assert request.inputs["output_name"] == "hype.mp4"
    assert calls[0][1].id == "local.hype-render"
    ledgers = sorted(projects_root.rglob("run.json"))
    assert ledgers == [projects_root / "demo" / "runs" / "hype-parent" / "run.json"]
