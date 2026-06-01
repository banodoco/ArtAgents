from __future__ import annotations

import importlib
import importlib.util
import json
import pkgutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest


SDK_MODULE_MISSING = importlib.util.find_spec("astrid.sdk") is None

pytestmark = pytest.mark.skipif(
    SDK_MODULE_MISSING,
    reason="public SDK facade lands in later execution batches",
)


EXPECTED_PUBLIC_NAMES = (
    "discover",
    "get_capability",
    "invoke",
    "Capability",
    "DiscoveryResult",
    "InvocationResult",
    "AstridSDKError",
    "CapabilityNotFoundError",
    "CapabilityAmbiguousError",
    "UnsupportedCapabilityError",
    "CapabilityInvocationError",
    "CapabilityHandle",
    "Port",
    "Output",
    "AliasRecord",
    "Provenance",
    "SafetyDeclaration",
    "ExecError",
)

HEAVY_MODULES = (
    "astrid.sdk",
    "astrid.core.executor.registry",
    "astrid.core.executor.runner",
    "astrid.core.orchestrator.registry",
    "astrid.core.orchestrator.runner",
)

REPRESENTATIVE_SUBMODULES = (
    "astrid.timeline",
    "astrid.pipeline",
    "astrid.doctor",
    "astrid.setup_cli",
)


def _fresh_import_probe() -> dict[str, Any]:
    script = """
import importlib
import json
import sys

astrid = importlib.import_module("astrid")
payload = {
    "all": list(astrid.__all__),
    "sdk_loaded": "astrid.sdk" in sys.modules,
    "heavy_loaded": {
        name: (name in sys.modules)
        for name in (
            "astrid.core.executor.registry",
            "astrid.core.executor.runner",
            "astrid.core.orchestrator.registry",
            "astrid.core.orchestrator.runner",
        )
    },
}
print(json.dumps(payload))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _import_public_module():
    return importlib.import_module("astrid")


def _make_capability(astrid_module, capability_id: str, capability_type: str) -> Any:
    return astrid_module.Capability(
        id=capability_id,
        capability_type=capability_type,
        native_kind=capability_type,
        handle=astrid_module.CapabilityHandle(
            canonical_id=capability_id,
            local_id=capability_id.rsplit(".", 1)[-1].split("/", 1)[-1],
            pack_id=capability_id.split(".", 1)[0] if "." in capability_id else "",
            kind=capability_type,
            name=capability_id,
            version="1.0.0",
            provenance=astrid_module.Provenance(source="test"),
        ),
    )


def test_import_astrid_exposes_exact_curated_sdk_names() -> None:
    probe = _fresh_import_probe()

    assert tuple(probe["all"]) == EXPECTED_PUBLIC_NAMES
    assert probe["sdk_loaded"] is False
    assert probe["heavy_loaded"] == {
        "astrid.core.executor.registry": False,
        "astrid.core.executor.runner": False,
        "astrid.core.orchestrator.registry": False,
        "astrid.core.orchestrator.runner": False,
    }


def test_curated_sdk_names_do_not_shadow_existing_top_level_modules() -> None:
    astrid = _import_public_module()
    top_level_modules = {name for _, name, _ in pkgutil.iter_modules(astrid.__path__)}
    collisions = sorted(top_level_modules.intersection(EXPECTED_PUBLIC_NAMES))

    assert collisions == []


def test_legacy_top_level_submodule_imports_still_resolve() -> None:
    for module_name in REPRESENTATIVE_SUBMODULES:
        imported = importlib.import_module(module_name)
        assert imported is not None


def test_discover_and_get_capability_expose_public_dtos() -> None:
    astrid = _import_public_module()

    inventory = astrid.discover(include_installed=False)
    assert tuple(astrid.__all__) == EXPECTED_PUBLIC_NAMES
    assert isinstance(inventory.executors, tuple)
    assert isinstance(inventory.orchestrators, tuple)
    assert isinstance(inventory.elements, tuple)
    assert isinstance(inventory.capabilities, tuple)
    assert inventory.executors
    assert inventory.orchestrators
    assert inventory.elements
    assert inventory.capabilities
    json.dumps(inventory.to_dict())

    aliased_executor = astrid.get_capability(
        "editorial.inspect_cut",
        kind="executor",
        include_installed=False,
    )
    aliased_orchestrator = astrid.get_capability(
        "video_editing.hype",
        kind="orchestrator",
        include_installed=False,
    )

    executor = astrid.get_capability(
        "editorial.arrange",
        kind="executor",
        include_installed=False,
    )
    kindless_executor = astrid.get_capability(
        "editorial.arrange",
        include_installed=False,
    )
    orchestrator = astrid.get_capability(
        "video_editing.hype",
        kind="orchestrator",
        include_installed=False,
    )
    kindless_orchestrator = astrid.get_capability(
        "video_editing.hype",
        include_installed=False,
    )
    element = astrid.get_capability(
        "effects/text-card",
        kind="element",
        include_installed=False,
    )
    explicit_element = astrid.get_capability(
        "text-card",
        kind="element",
        element_kind="effects",
        include_installed=False,
    )
    kindless_element = astrid.get_capability(
        "effects/text-card",
        include_installed=False,
    )

    assert executor.id == "editorial.arrange"
    assert kindless_executor.id == "editorial.arrange"
    assert executor.capability_type == "executor"
    assert executor.native_kind in {"built_in", "external"}
    assert isinstance(executor.handle, astrid.CapabilityHandle)
    assert isinstance(executor.inputs, tuple)
    assert isinstance(executor.outputs, tuple)
    assert isinstance(executor.schema, dict)
    assert isinstance(executor.definition, dict)
    assert executor.defaults == {}
    json.dumps(executor.to_dict())

    assert [alias.alias for alias in aliased_executor.handle.aliases] == ["builtin.inspect_cut"]
    assert aliased_executor.handle.aliases[0].deprecated is True

    assert orchestrator.id == "video_editing.hype"
    assert kindless_orchestrator.id == "video_editing.hype"
    assert orchestrator.capability_type == "orchestrator"
    assert orchestrator.native_kind in {"built_in", "external"}
    assert isinstance(orchestrator.handle, astrid.CapabilityHandle)
    assert isinstance(orchestrator.inputs, tuple)
    assert isinstance(orchestrator.outputs, tuple)
    assert isinstance(orchestrator.schema, dict)
    assert isinstance(orchestrator.definition, dict)
    assert orchestrator.defaults == {}
    json.dumps(orchestrator.to_dict())

    assert [alias.alias for alias in aliased_orchestrator.handle.aliases] == ["builtin.hype"]
    assert aliased_orchestrator.handle.aliases[0].deprecated is True

    assert element.id == "effects/text-card"
    assert explicit_element.id == "effects/text-card"
    assert kindless_element.id == "effects/text-card"
    assert element.capability_type == "element"
    assert element.native_kind == "effects"
    assert isinstance(element.handle, astrid.CapabilityHandle)
    assert element.inputs == ()
    assert element.outputs == ()
    assert isinstance(element.schema, dict)
    assert isinstance(element.defaults, dict)
    assert isinstance(element.definition, dict)
    json.dumps(element.to_dict())


def test_discover_loads_registries_in_dependency_order_and_flattens_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    calls: list[tuple[str, dict[str, Any]]] = []

    class _FakeRegistry:
        def __init__(self, items: tuple[str, ...]) -> None:
            self._items = items
            self.alias_resolver = None

        def list(self) -> tuple[str, ...]:
            return self._items

    executor_registry = _FakeRegistry(("editorial.inspect_cut",))
    orchestrator_registry = _FakeRegistry(("video_editing.hype",))
    element_registry = _FakeRegistry(("effects/text-card",))
    banodoco_config = object()
    active_theme = tmp_path / "theme"

    def fake_load_executor_registry(**kwargs: Any) -> _FakeRegistry:
        calls.append(("executor", kwargs))
        return executor_registry

    def fake_load_orchestrator_registry(**kwargs: Any) -> _FakeRegistry:
        calls.append(("orchestrator", kwargs))
        assert kwargs["executor_registry"] is executor_registry
        return orchestrator_registry

    def fake_load_element_registry(**kwargs: Any) -> _FakeRegistry:
        calls.append(("element", kwargs))
        return element_registry

    monkeypatch.setattr(sdk, "_load_executor_registry", fake_load_executor_registry)
    monkeypatch.setattr(sdk, "_load_orchestrator_registry", fake_load_orchestrator_registry)
    monkeypatch.setattr(sdk, "_load_element_registry", fake_load_element_registry)
    monkeypatch.setattr(
        sdk,
        "_capability_from_executor",
        lambda definition, registry: _make_capability(astrid, definition, "executor"),
    )
    monkeypatch.setattr(
        sdk,
        "_capability_from_orchestrator",
        lambda definition, registry: _make_capability(astrid, definition, "orchestrator"),
    )
    monkeypatch.setattr(
        sdk,
        "_capability_from_element",
        lambda definition: _make_capability(astrid, definition, "element"),
    )

    inventory = astrid.discover(
        project_root=tmp_path,
        extra_pack_roots=("extra/packs",),
        include_installed=False,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=True,
    )

    assert [name for name, _ in calls] == ["executor", "orchestrator", "element"]
    assert calls[0][1] == {
        "project_root": tmp_path,
        "extra_pack_roots": ("extra/packs",),
        "include_installed": False,
        "banodoco_config": banodoco_config,
    }
    assert calls[1][1] == {
        "executor_registry": executor_registry,
        "project_root": tmp_path,
        "extra_pack_roots": ("extra/packs",),
        "include_installed": False,
        "banodoco_config": banodoco_config,
    }
    assert calls[2][1] == {
        "project_root": tmp_path,
        "extra_pack_roots": ("extra/packs",),
        "include_installed": False,
        "active_theme": active_theme,
        "include_missing_roots": True,
    }
    assert tuple(capability.id for capability in inventory.executors) == ("editorial.inspect_cut",)
    assert tuple(capability.id for capability in inventory.orchestrators) == ("video_editing.hype",)
    assert tuple(capability.id for capability in inventory.elements) == ("effects/text-card",)
    assert tuple(capability.id for capability in inventory.capabilities) == (
        "editorial.inspect_cut",
        "video_editing.hype",
        "effects/text-card",
    )


def test_get_capability_raises_typed_lookup_errors() -> None:
    astrid = _import_public_module()

    with pytest.raises(astrid.CapabilityNotFoundError):
        astrid.get_capability(
            "missing.capability",
            kind="executor",
            include_installed=False,
        )

    with pytest.raises(astrid.CapabilityAmbiguousError):
        astrid.get_capability(
            "fade",
            kind="element",
            include_installed=False,
        )

    with pytest.raises(astrid.CapabilityAmbiguousError, match="animations/fade.*transitions/fade"):
        astrid.get_capability(
            "fade",
            include_installed=False,
        )


def test_invoke_rejects_elements_and_missing_executor_out() -> None:
    astrid = _import_public_module()

    with pytest.raises(astrid.UnsupportedCapabilityError):
        astrid.invoke(
            "effects/text-card",
            kind="element",
            include_installed=False,
        )

    with pytest.raises(astrid.CapabilityInvocationError):
        astrid.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
        )


@dataclass(frozen=True)
class _FakeExecutorResult:
    executor_id: str
    kind: str
    command: tuple[str, ...]
    cwd: Path
    env: MappingProxyType[str, str]
    payload: MappingProxyType[str, Any]
    returncode: int | None = 0
    dry_run: bool = False
    skipped: bool = False
    skipped_reason: str = ""
    missing_binaries: tuple[str, ...] = ()
    error: object | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class _FakeOrchestratorResult:
    def __init__(self) -> None:
        self.ok = True
        self.errors = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "orchestrator_id": "video_editing.hype",
            "kind": "built_in",
            "runtime_kind": "python",
            "command": ["python", "-m", "astrid", "orchestrators", "run", "video_editing.hype"],
            "planned_commands": [["python", "-m", "astrid", "orchestrators", "run", "video_editing.hype"]],
            "cwd": str(Path("/tmp/orchestrator")),
            "env": {"ASTRID_SAMPLE": "1"},
            "returncode": 0,
            "dry_run": True,
            "outputs": {"plan": "ok"},
            "errors": [],
            "plan": {"steps": [], "summary": "ok"},
            "ok": True,
        }


def test_invoke_executor_builds_request_and_normalizes_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    seen: dict[str, Any] = {}

    def fake_run_executor(request: Any, registry: Any) -> _FakeExecutorResult:
        seen["request"] = request
        seen["registry"] = registry
        return _FakeExecutorResult(
            executor_id=request.executor_id,
            kind="built_in",
            command=("python", "-m", "astrid", "executors", "run", request.executor_id),
            cwd=Path("/tmp/executor"),
            env=MappingProxyType({"ASTRID_SAMPLE": "1"}),
            payload=MappingProxyType({"artifact": tmp_path / "artifact.json"}),
            returncode=0,
            dry_run=request.dry_run,
            error=astrid.ExecError(code="ok", type="none", message=""),
        )

    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    result = astrid.invoke(
        "editorial.arrange",
        kind="executor",
        include_installed=False,
        out=tmp_path,
        project="demo-project",
        inputs={"brief": "demo"},
        outputs={"artifact": "artifact.json"},
        brief=tmp_path / "brief.md",
        dry_run=True,
        check_binaries=True,
        python_exec=sys.executable,
        verbose=True,
        argv=("executors", "run", "editorial.arrange"),
    )

    request = seen["request"]
    assert request.executor_id == "editorial.arrange"
    assert request.out == tmp_path
    assert request.project == "demo-project"
    assert request.inputs == {"brief": "demo"}
    assert request.outputs == {"artifact": "artifact.json"}
    assert request.brief == tmp_path / "brief.md"
    assert request.dry_run is True
    assert request.check_binaries is True
    assert request.python_exec == sys.executable
    assert request.verbose is True
    assert request.argv == ("executors", "run", "editorial.arrange")
    assert seen["registry"] is not None

    assert result.capability_id == "editorial.arrange"
    assert result.capability_type == "executor"
    assert result.native_kind in {"built_in", "external"}
    assert result.ok is False
    assert result.error == {"code": "ok", "type": "none", "message": "", "recovery": ""}
    assert result.raw_result["cwd"] == "/tmp/executor"
    assert result.raw_result["payload"] == {"artifact": str(tmp_path / "artifact.json")}
    assert result.raw_result["env"] == {"ASTRID_SAMPLE": "1"}
    json.dumps(result.to_dict())


def test_invoke_orchestrator_builds_request_and_normalizes_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    seen: dict[str, Any] = {}

    def fake_run_orchestrator(request: Any, registry: Any) -> _FakeOrchestratorResult:
        seen["request"] = request
        seen["registry"] = registry
        return _FakeOrchestratorResult()

    monkeypatch.setattr(sdk, "run_orchestrator", fake_run_orchestrator)

    result = astrid.invoke(
        "video_editing.hype",
        kind="orchestrator",
        include_installed=False,
        out=tmp_path,
        project="demo-project",
        inputs={"video": "input.mp4"},
        outputs={"plan": "plan.json"},
        brief=tmp_path / "brief.md",
        dry_run=True,
        python_exec=sys.executable,
        verbose=True,
        orchestrator_args=("--render",),
    )

    request = seen["request"]
    assert request.orchestrator_id == "video_editing.hype"
    assert request.out == tmp_path
    assert request.project == "demo-project"
    assert request.inputs == {"video": "input.mp4"}
    assert request.outputs == {"plan": "plan.json"}
    assert request.brief == tmp_path / "brief.md"
    assert request.orchestrator_args == ("--render",)
    assert request.dry_run is True
    assert request.python_exec == sys.executable
    assert request.verbose is True
    assert seen["registry"] is not None

    assert result.capability_id == "video_editing.hype"
    assert result.capability_type == "orchestrator"
    assert result.native_kind in {"built_in", "external"}
    assert result.ok is True
    assert result.error is None
    assert result.raw_result["outputs"] == {"plan": "ok"}
    assert result.raw_result["planned_commands"] == [
        ["python", "-m", "astrid", "orchestrators", "run", "video_editing.hype"]
    ]
    json.dumps(result.to_dict())


def test_invoke_reuses_loaded_registries_and_preserves_runner_exception_cause(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    executor_registry = object()
    orchestrator_registry = object()
    registries = (executor_registry, orchestrator_registry, None)
    seen: dict[str, Any] = {"load_calls": 0}

    def fake_load_registries(**kwargs: Any) -> tuple[object, object, None]:
        seen["load_calls"] += 1
        return registries

    def fake_get_capability(capability_id: str, **kwargs: Any) -> Any:
        assert capability_id == "editorial.arrange"
        assert kwargs["_registries"] is registries
        return _make_capability(astrid, capability_id, "executor")

    def fake_run_executor(request: Any, registry: Any) -> Any:
        assert registry is executor_registry
        raise ValueError("boom")

    monkeypatch.setattr(sdk, "_load_registries", fake_load_registries)
    monkeypatch.setattr(sdk, "get_capability", fake_get_capability)
    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    with pytest.raises(astrid.CapabilityInvocationError) as excinfo:
        astrid.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
            out=tmp_path,
        )

    assert seen["load_calls"] == 1
    assert isinstance(excinfo.value.__cause__, ValueError)
    assert str(excinfo.value.__cause__) == "boom"
