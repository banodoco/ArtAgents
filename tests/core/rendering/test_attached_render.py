from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.rendering import attached
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV


def test_attached_render_has_no_local_kernel_sqlite_authority_path() -> None:
    source = Path(attached.__file__).read_text(encoding="utf-8")
    assert "kernel_run_info" not in source
    assert "import sqlite3" not in source


class _Registry:
    def __init__(self, resolved_id: str = "rendering.render") -> None:
        self.resolved_id = resolved_id

    def get(self, executor_id: str) -> SimpleNamespace:
        assert executor_id == "rendering.render"
        return SimpleNamespace(id=self.resolved_id)


class _Service:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def render(self, *args: object, **kwargs: object) -> Path:
        self.calls.append((args, kwargs))
        output = Path(args[2])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"public")
        return output


def _seed_parent(root: Path) -> None:
    # The parent is owned by the neutral runtime fixture; this test only
    # supplies its explicit project directory and mocks the runtime lookup.
    root.mkdir(parents=True, exist_ok=True)


class _RuntimeClient:
    def __init__(self, *, run_id: str = "parent-run", valid: bool = True) -> None:
        self.run_id = run_id
        self.valid = valid
        self.runs = self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def show(self, run_id: str):
        if not self.valid or run_id != self.run_id:
            return SimpleNamespace(ok=False, data=None)
        return SimpleNamespace(
            ok=True,
            data={"project_id": "demo", "run_id": run_id, "status": "running"},
        )


def _patch_runtime_parent(
    monkeypatch: pytest.MonkeyPatch, *, run_id: str = "parent-run", valid: bool = True
) -> None:
    monkeypatch.setattr(
        "astrid.sdk.client.AstridClient.open",
        classmethod(lambda cls: _RuntimeClient(run_id=run_id, valid=valid)),
    )


def _fake_success(calls: list[object], *, marker: bytes = b"attached"):
    def invoke(request, registry):
        calls.append((request, registry.get(request.executor_id), dict(os.environ)))
        output = Path(request.out) / request.inputs["output_name"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(marker)
        sidecar = Path(f"{output}.provenance.json")
        sidecar.write_text("{}\n", encoding="utf-8")
        return SimpleNamespace(
            ok=True,
            error=None,
            outputs={"video": str(output), "provenance": str(sidecar)},
        )

    return invoke


def test_attached_invocation_records_unique_child_step_and_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    _seed_parent(projects_root)
    _patch_runtime_parent(monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(attached, "run_executor", _fake_success(calls))
    output = tmp_path / "chosen" / "preview.mp4"

    result = attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        output,
        project_slug="demo",
        parent_run_id="parent-run",
        step_id="render-preview",
        root=projects_root,
        executor_registry=_Registry(),
    )

    assert result == output.resolve()
    produces = (
        projects_root
        / ".astrid-runtime-staging"
        / "demo"
        / "parent-run"
        / "steps"
        / "render-preview"
        / "v1"
        / "produces"
    )
    assert (produces / "preview.mp4").resolve() == output.resolve()
    assert (produces / "preview.mp4.provenance.json").resolve() == Path(
        f"{output.resolve()}.provenance.json"
    )
    # Parent validation is runtime-backed; no legacy project run.json is
    # required to attach the child render.
    assert not list(projects_root.rglob("run.json"))
    with pytest.raises(attached.AttachedRenderError, match="already exists"):
        attached.invoke_attached_render(
            tmp_path / "timeline.json",
            tmp_path / "assets.json",
            output,
            project_slug="demo",
            parent_run_id="parent-run",
            step_id="render-preview",
            root=projects_root,
            executor_registry=_Registry(),
        )


def test_task_env_is_scoped_and_restored_after_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    _seed_parent(projects_root)
    _patch_runtime_parent(monkeypatch)
    monkeypatch.setenv(TASK_PROJECT_ENV, "outer-project")
    monkeypatch.delenv(TASK_RUN_ID_ENV, raising=False)
    monkeypatch.setenv(TASK_STEP_ID_ENV, "")
    calls: list[object] = []
    monkeypatch.setattr(attached, "run_executor", _fake_success(calls))

    attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        tmp_path / "out" / "success.mp4",
        project_slug="demo",
        parent_run_id="parent-run",
        step_id="success-child",
        root=projects_root,
        executor_registry=_Registry(),
    )

    scoped = calls[0][2]
    assert scoped[TASK_PROJECT_ENV] == "demo"
    assert scoped[TASK_RUN_ID_ENV] == "parent-run"
    assert scoped[TASK_STEP_ID_ENV] == "success-child"
    assert os.environ[TASK_PROJECT_ENV] == "outer-project"
    assert TASK_RUN_ID_ENV not in os.environ
    assert os.environ[TASK_STEP_ID_ENV] == ""


def test_task_env_is_scoped_and_restored_after_child_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    _seed_parent(projects_root)
    _patch_runtime_parent(monkeypatch)
    monkeypatch.delenv(TASK_PROJECT_ENV, raising=False)
    monkeypatch.setenv(TASK_RUN_ID_ENV, "outer-run")
    monkeypatch.setenv(TASK_STEP_ID_ENV, "outer-step")
    observed: dict[str, str] = {}

    def fail(_request, _registry):
        observed.update(
            {
                name: os.environ[name]
                for name in (TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV)
            }
        )
        raise RuntimeError("child exploded")

    monkeypatch.setattr(attached, "run_executor", fail)

    with pytest.raises(RuntimeError, match="child exploded"):
        attached.invoke_attached_render(
            tmp_path / "timeline.json",
            tmp_path / "assets.json",
            tmp_path / "out" / "failure.mp4",
            project_slug="demo",
            parent_run_id="parent-run",
            step_id="failure-child",
            root=projects_root,
            executor_registry=_Registry(),
        )

    assert observed == {
        TASK_PROJECT_ENV: "demo",
        TASK_RUN_ID_ENV: "parent-run",
        TASK_STEP_ID_ENV: "failure-child",
    }
    assert TASK_PROJECT_ENV not in os.environ
    assert os.environ[TASK_RUN_ID_ENV] == "outer-run"
    assert os.environ[TASK_STEP_ID_ENV] == "outer-step"


def test_caller_selected_output_name_is_forwarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    _seed_parent(projects_root)
    _patch_runtime_parent(monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(attached, "run_executor", _fake_success(calls))
    output = tmp_path / "deliverables" / "iteration.mp4"

    attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        output,
        project_slug="demo",
        parent_run_id="parent-run",
        step_id="iteration-render",
        root=projects_root,
        executor_registry=_Registry(),
    )

    request = calls[0][0]
    assert Path(request.out) == output.parent.resolve()
    assert request.inputs["output_name"] == "iteration.mp4"
    assert output.read_bytes() == b"attached"


def test_executor_override_changes_attached_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    _seed_parent(projects_root)
    _patch_runtime_parent(monkeypatch)
    calls: list[object] = []

    def invoke(request, registry):
        resolved = registry.get(request.executor_id)
        output = Path(request.out) / request.inputs["output_name"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(resolved.id, encoding="utf-8")
        sidecar = Path(f"{output}.provenance.json")
        sidecar.write_text("{}\n", encoding="utf-8")
        calls.append(resolved.id)
        return SimpleNamespace(
            ok=True,
            error=None,
            outputs={"video": str(output), "provenance": str(sidecar)},
        )

    monkeypatch.setattr(attached, "run_executor", invoke)
    output = tmp_path / "out" / "override.mp4"

    attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        output,
        project_slug="demo",
        parent_run_id="parent-run",
        step_id="overridden-render",
        root=projects_root,
        executor_registry=_Registry("local.custom-render"),
    )

    assert calls == ["local.custom-render"]
    assert output.read_text(encoding="utf-8") == "local.custom-render"


def test_unbound_falls_back_to_public_service_without_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The autouse suite sandbox already creates ``tmp_path / "projects"``;
    # use a never-created caller-owned root so this test proves the unbound
    # fallback does not initialize it.
    projects_root = tmp_path / "unbound-projects"
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    for name in (TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV):
        monkeypatch.delenv(name, raising=False)
    service = _Service()
    output = tmp_path / "public" / "standalone.mp4"

    result = attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        output,
        selector="rendering.fixture",
        service=service,
    )

    assert result == output
    assert len(service.calls) == 1
    assert service.calls[0][1]["selector"] == "rendering.fixture"
    assert not projects_root.exists()
    assert not list(tmp_path.rglob("run.json"))


def test_bound_with_invalid_parent_is_rejected_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    _patch_runtime_parent(monkeypatch, run_id="missing-run", valid=False)
    service = _Service()
    invoked = False

    def should_not_run(*_args, **_kwargs):
        nonlocal invoked
        invoked = True

    monkeypatch.setattr(attached, "run_executor", should_not_run)

    with pytest.raises(attached.AttachedRenderError, match="invalid runtime parent"):
        attached.invoke_attached_render(
            tmp_path / "timeline.json",
            tmp_path / "assets.json",
            tmp_path / "out" / "invalid.mp4",
            project_slug="demo",
            parent_run_id="missing-run",
            step_id="render",
            root=projects_root,
            executor_registry=_Registry(),
            service=service,
        )

    assert not invoked
    assert service.calls == []
    assert not (projects_root / "demo" / "runs" / "missing-run").exists()
