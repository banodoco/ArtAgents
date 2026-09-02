from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.contracts.run_status import RunStatus
from astrid.core.pack.override import OverrideStore
from astrid.core.project.project import create_project
from astrid.core.project.run import write_run_record
from astrid.core.rendering import attached
from astrid.core.rendering.provenance import assemble_provenance_v2
from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.packs.rendering.executors.render import run as render_facade
from tests.core.rendering.test_provenance import _lineage_service
from tests.core.rendering.test_service import (
    FakeTransport,
    _finalizer_resolution,
    _plan,
    _request,
)


def test_executor_override_affects_attached_facade_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    create_project("demo", root=projects_root)
    write_run_record(
        "demo",
        "parent-run",
        root=projects_root,
        tool_id="demo.parent",
        kind="orchestrator",
        status=RunStatus.RUNNING,
    )
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))

    from astrid.core.execution.executor.registry import load_default_registry

    baseline = load_default_registry()
    original = baseline.get("rendering.render")
    overridden = replace(original, id="local.render-override")
    override_store = OverrideStore(tmp_path / "override-project")
    override_store.set_override("executor", "rendering.render", "local.render-override")
    registry = ExecutorRegistry(override_store=override_store)
    registry.register(original)
    registry.register(overridden)
    resolved_ids: list[str] = []

    def fake_run(request, selected_registry):
        resolved = selected_registry.get(request.executor_id)
        resolved_ids.append(resolved.id)
        output = Path(request.out) / request.inputs["output_name"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"override")
        sidecar = Path(f"{output}.provenance.json")
        sidecar.write_text("{}\n", encoding="utf-8")
        return SimpleNamespace(
            ok=True,
            error=None,
            outputs={"video": str(output), "provenance": str(sidecar)},
        )

    monkeypatch.setattr(attached, "run_executor", fake_run)
    attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        tmp_path / "out" / "hype.mp4",
        project_slug="demo",
        parent_run_id="parent-run",
        step_id="override-render",
        executor_registry=registry,
    )

    assert resolved_ids == ["local.render-override"]


@pytest.mark.parametrize("caller", ["facade", "service"])
def test_rendering_overrides_affect_facade_and_public_service_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caller: str
) -> None:
    transport = FakeTransport()
    transport.plan = replace(
        _plan("lineage.renderer-v2"),
        finalizer=_finalizer_resolution("lineage.finalizer-alias"),
    )
    service = _lineage_service(
        tmp_path,
        transport,
        provenance_builder=assemble_provenance_v2,
    )
    request = _request(tmp_path)
    output = tmp_path / caller / "video.mp4"

    if caller == "facade":
        monkeypatch.setattr(render_facade, "_default_service", lambda: service)
        render_facade.render(
            Path(request.timeline_path),
            Path(request.assets_registry_path or ""),
            output,
            engine="rendering.legacy_hybrid",
        )
    else:
        service.render(
            Path(request.timeline_path),
            Path(request.assets_registry_path or ""),
            output,
            selector="rendering.legacy_hybrid",
        )

    provenance = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    assert provenance["planner"]["override"] == {
        "from": "lineage.planner",
        "to": "lineage.planner-v2",
    }
    assert provenance["segments_v2"][0]["renderer"]["override"] == {
        "from": "lineage.renderer-v2",
        "to": "lineage.renderer-v3",
    }
    assert provenance["finalizer"]["override"] == {
        "from": "lineage.finalizer",
        "to": "lineage.finalizer-v2",
    }
