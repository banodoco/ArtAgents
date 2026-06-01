from __future__ import annotations

import importlib
import importlib.util
import json
import pkgutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from astrid.contracts.event_log_error import EventLogError
from astrid.core.executor.schema import ExecutorValidationError
from astrid.core.orchestrator.runner import OrchestratorRunError
from astrid.core.session.lease import LeaseError
from astrid.core.task.events import NotWriterError, StaleEpochError, StaleTailError


SDK_MODULE_MISSING = importlib.util.find_spec("astrid.sdk") is None

pytestmark = pytest.mark.skipif(
    SDK_MODULE_MISSING,
    reason="public SDK facade lands in later execution batches",
)


EXPECTED_PUBLIC_NAMES = (
    "discover",
    "get_capability",
    "invoke",
    "read_events",
    "subscribe_events",
    "Capability",
    "DiscoveryResult",
    "EventStreamRecord",
    "InvocationResult",
    "AstridSDKError",
    "CapabilityNotFoundError",
    "CapabilityAmbiguousError",
    "CapabilityValidationError",
    "CapabilityMissingInputError",
    "CapabilityPreconditionError",
    "CapabilityRuntimeError",
    "CapabilityLeaseError",
    "CapabilityEventLogError",
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
    assert inventory.packs
    assert inventory.generation_backends
    assert inventory.element_kinds
    assert inventory.generation_features
    assert inventory.generation_modes
    json.dumps(inventory.to_dict())

    assert any(pack["id"] == "builtin" for pack in inventory.packs)
    assert all("source_kind" in pack for pack in inventory.packs)
    assert any(backend["id"] == "local" for backend in inventory.generation_backends)
    assert any(backend["id"] == "cloud" for backend in inventory.generation_backends)
    assert any(kind["canonical_kind"] == "effects" for kind in inventory.element_kinds)
    assert any(feature["id"] == "prompt" for feature in inventory.generation_features)
    assert any(mode["id"] == "t2i" for mode in inventory.generation_modes)

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
    monkeypatch.setattr(sdk, "_discover_pack_inventory", lambda **kwargs: ("discovered-pack",))
    monkeypatch.setattr(
        sdk,
        "_build_discovery_metadata",
        lambda discovered_packs, *, element_registry: (
            ({"id": "builtin", "source_kind": "source", "priority_index": 0},),
            ({"id": "local"},),
            ({"canonical_kind": "effects"},),
            ({"id": "prompt"},),
            ({"id": "t2i"},),
        ),
    )
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
    assert inventory.packs == ({"id": "builtin", "source_kind": "source", "priority_index": 0},)
    assert inventory.generation_backends == ({"id": "local"},)
    assert inventory.element_kinds == ({"canonical_kind": "effects"},)
    assert inventory.generation_features == ({"id": "prompt"},)
    assert inventory.generation_modes == ({"id": "t2i"},)


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


def test_get_capability_supports_pack_declared_element_kinds_and_invalid_kind_errors() -> None:
    astrid = _import_public_module()

    with tempfile.TemporaryDirectory() as tmp:
        packs_root = Path(tmp) / "packs"
        pack_root = packs_root / "demo"
        pack_root.mkdir(parents=True)
        (pack_root / "pack.json").write_text(
            json.dumps(
                {
                    "id": "demo",
                    "name": "Demo Pack",
                    "version": "0.1.0",
                    "schema_version": "1",
                    "extensions": {
                        "elements": {
                            "kinds": [
                                {"id": "widgets", "singular": "widget"},
                            ]
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        element_root = pack_root / "elements" / "widgets" / "glow"
        element_root.mkdir(parents=True)
        (element_root / "component.tsx").write_text(
            "export default function Glow() { return null; }\n",
            encoding="utf-8",
        )
        (element_root / "element.yaml").write_text(
            json.dumps(
                {
                    "id": "glow",
                    "kind": "widget",
                    "pack_id": "demo",
                    "metadata": {"label": "Glow"},
                    "schema": {"type": "object"},
                    "defaults": {"enabled": True},
                    "dependencies": {"js_packages": [], "python_requirements": []},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        capability = astrid.get_capability(
            "widget/glow",
            kind="element",
            include_installed=False,
            extra_pack_roots=(str(packs_root),),
        )

        explicit_kind_capability = astrid.get_capability(
            "glow",
            kind="element",
            element_kind="widget",
            include_installed=False,
            extra_pack_roots=(str(packs_root),),
        )

        assert capability.id == "widgets/glow"
        assert capability.handle.kind == "widgets"
        assert explicit_kind_capability.id == "widgets/glow"
        assert explicit_kind_capability.handle.kind == "widgets"

        with pytest.raises(
            astrid.CapabilityValidationError,
            match=r"element kind must be one of \[effects, animations, transitions, widgets\]",
        ):
            astrid.get_capability(
                "wigdet/glow",
                kind="element",
                include_installed=False,
                extra_pack_roots=(str(packs_root),),
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


def test_discover_exposes_pack_declared_extension_metadata() -> None:
    astrid = _import_public_module()

    with tempfile.TemporaryDirectory() as tmp:
        packs_root = Path(tmp) / "packs"
        pack_root = packs_root / "demo"
        pack_root.mkdir(parents=True)
        (pack_root / "pack.json").write_text(
            json.dumps(
                {
                    "id": "demo",
                    "name": "Demo Pack",
                    "version": "0.1.0",
                    "schema_version": "1",
                    "extensions": {
                        "generation": {
                            "backends": [
                                {
                                    "id": "studio",
                                    "module": "demo_backend.module",
                                    "class": "StudioBackend",
                                    "label": "Studio Backend",
                                    "init_kwargs": {"region": "eu"},
                                }
                            ],
                            "features": [
                                {
                                    "id": "mask_ref",
                                    "label": "Mask Ref",
                                    "description": "Mask input.",
                                }
                            ],
                            "modes": [
                                {
                                    "id": "style-transfer",
                                    "label": "Style Transfer",
                                    "description": "Apply a style reference.",
                                }
                            ],
                        },
                        "elements": {
                            "kinds": [
                                {
                                    "id": "widgets",
                                    "singular": "widget",
                                    "label": "Widgets",
                                    "description": "Custom widget elements.",
                                }
                            ]
                        },
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        element_root = pack_root / "elements" / "widgets" / "glow"
        element_root.mkdir(parents=True)
        (element_root / "component.tsx").write_text(
            "export default function Glow() { return null; }\n",
            encoding="utf-8",
        )
        (element_root / "element.yaml").write_text(
            json.dumps(
                {
                    "id": "glow",
                    "kind": "widget",
                    "pack_id": "demo",
                    "metadata": {"label": "Glow"},
                    "schema": {"type": "object"},
                    "defaults": {"enabled": True},
                    "dependencies": {"js_packages": [], "python_requirements": []},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        inventory = astrid.discover(
            include_installed=False,
            extra_pack_roots=(str(packs_root),),
        )

        demo_pack = next(pack for pack in inventory.packs if pack["id"] == "demo")
        studio_backend = next(
            backend for backend in inventory.generation_backends if backend["id"] == "studio"
        )
        widget_kind = next(
            kind for kind in inventory.element_kinds if kind["canonical_kind"] == "widgets"
        )
        mask_ref_feature = next(
            feature for feature in inventory.generation_features if feature["id"] == "mask_ref"
        )
        style_transfer_mode = next(
            mode for mode in inventory.generation_modes if mode["id"] == "style-transfer"
        )

        assert demo_pack["source_kind"] == "extra"
        assert demo_pack["priority_index"] >= 0
        assert demo_pack["extensions"]["generation"]["backends"][0]["id"] == "studio"
        assert studio_backend == {
            "id": "studio",
            "label": "Studio Backend",
            "module": "demo_backend.module",
            "class": "StudioBackend",
            "init_kwargs": {"region": "eu"},
        }
        assert widget_kind["id"] == "widgets"
        assert widget_kind["canonical_kind"] == "widgets"
        assert widget_kind["aliases"] == ["widgets", "widget"]
        assert mask_ref_feature == {
            "id": "mask_ref",
            "label": "Mask Ref",
            "description": "Mask input.",
        }
        assert style_transfer_mode == {
            "id": "style-transfer",
            "modalities": [],
            "label": "Style Transfer",
            "description": "Apply a style reference.",
        }
        json.dumps(inventory.to_dict())


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
        execution_mode="in_process",
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
    assert request.execution_mode == "in_process"
    assert request.argv == ("executors", "run", "editorial.arrange")
    assert seen["registry"] is not None

    assert result.capability_id == "editorial.arrange"
    assert result.capability_type == "executor"
    assert result.native_kind in {"built_in", "external"}
    assert result.ok is False
    assert result.error == {
        "code": "ok",
        "type": "none",
        "message": "",
        "recovery": "",
        "sdk_error": "CapabilityInvocationError",
        "sdk_category": "invocation",
    }
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
        execution_mode="in_process",
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
    assert request.execution_mode == "in_process"
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


def test_invoke_defaults_to_subprocess_execution_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    seen: dict[str, Any] = {}

    def fake_run_executor(request: Any, registry: Any) -> _FakeExecutorResult:
        seen["request"] = request
        return _FakeExecutorResult(
            executor_id=request.executor_id,
            kind="built_in",
            command=("python", "-m", "astrid", "executors", "run", request.executor_id),
            cwd=Path("/tmp/executor"),
            env=MappingProxyType({}),
            payload=MappingProxyType({}),
            returncode=0,
        )

    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    result = astrid.invoke(
        "editorial.arrange",
        kind="executor",
        include_installed=False,
        out=tmp_path,
    )

    assert seen["request"].execution_mode == "subprocess"
    assert result.ok is True


def test_read_events_validates_project_and_resolves_run_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    with pytest.raises(astrid.CapabilityValidationError, match="project slug"):
        astrid.read_events("Bad Project", "run-1")

    run_dir = tmp_path / "resolved-run"
    seen: dict[str, Any] = {}
    expected_record = astrid.EventStreamRecord(
        source="task",
        line=1,
        timestamp="2026-01-01T00:00:00Z",
        kind="run_started",
        hash="sha256:abc",
        payload={"kind": "run_started"},
    )

    def fake_resolve(project: str, run_id: str, *, projects_root: Path | None = None) -> Path:
        seen["resolve"] = (project, run_id, projects_root)
        return run_dir

    def fake_read_event_stream(path: Path, *, include_audit: bool, verify: bool) -> list[Any]:
        seen["read"] = (path, include_audit, verify)
        return [expected_record]

    monkeypatch.setattr(sdk, "_resolve_event_stream_run_dir", fake_resolve)
    monkeypatch.setattr(sdk, "_read_task_event_stream", fake_read_event_stream)

    records = astrid.read_events(
        "demo-project",
        "run-1",
        projects_root=tmp_path / "projects",
        include_audit=False,
        verify=False,
    )

    assert records == (expected_record,)
    assert seen["resolve"] == ("demo-project", "run-1", tmp_path / "projects")
    assert seen["read"] == (run_dir, False, False)


def test_read_events_maps_missing_run_and_event_log_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")

    def missing_run(project: str, run_id: str, *, projects_root: Path | None = None) -> Path:
        raise FileNotFoundError(f"run {run_id!r} not found in project {project!r}")

    monkeypatch.setattr(sdk, "_resolve_event_stream_run_dir", missing_run)
    with pytest.raises(astrid.CapabilityPreconditionError, match="run 'run-1' not found"):
        astrid.read_events("demo", "run-1")

    run_dir = Path("/tmp/demo-run")

    def ok_resolve(project: str, run_id: str, *, projects_root: Path | None = None) -> Path:
        return run_dir

    def corrupt_read(path: Path, *, include_audit: bool, verify: bool) -> list[Any]:
        raise EventLogError("verification failed")

    monkeypatch.setattr(sdk, "_resolve_event_stream_run_dir", ok_resolve)
    monkeypatch.setattr(sdk, "_read_task_event_stream", corrupt_read)
    with pytest.raises(astrid.CapabilityEventLogError, match="verification failed"):
        astrid.read_events("demo", "run-1")


def test_subscribe_events_delegates_and_maps_iteration_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    run_dir = Path("/tmp/demo-run")
    seen: dict[str, Any] = {}
    expected_record = astrid.EventStreamRecord(
        source="task",
        line=2,
        timestamp="2026-01-01T00:00:01Z",
        kind="step_completed",
        hash="sha256:def",
        payload={"kind": "step_completed"},
    )

    def fake_resolve(project: str, run_id: str, *, projects_root: Path | None = None) -> Path:
        seen["resolve"] = (project, run_id, projects_root)
        return run_dir

    def fake_subscribe(
        path: Path,
        *,
        include_audit: bool,
        verify: bool,
        follow: bool,
        poll_interval: float,
        idle_polls: int | None,
    ):
        seen["subscribe"] = (path, include_audit, verify, follow, poll_interval, idle_polls)
        yield expected_record

    monkeypatch.setattr(sdk, "_resolve_event_stream_run_dir", fake_resolve)
    monkeypatch.setattr(sdk, "_subscribe_task_event_stream", fake_subscribe)

    records = list(
        astrid.subscribe_events(
            "demo",
            "run-1",
            follow=True,
            poll_interval=0,
            idle_polls=2,
        )
    )

    assert records == [expected_record]
    assert seen["resolve"] == ("demo", "run-1", None)
    assert seen["subscribe"] == (run_dir, True, True, True, 0, 2)

    def failing_subscribe(
        path: Path,
        *,
        include_audit: bool,
        verify: bool,
        follow: bool,
        poll_interval: float,
        idle_polls: int | None,
    ):
        raise EventLogError("stream corrupted")
        yield  # pragma: no cover

    monkeypatch.setattr(sdk, "_subscribe_task_event_stream", failing_subscribe)
    with pytest.raises(astrid.CapabilityEventLogError, match="stream corrupted"):
        list(astrid.subscribe_events("demo", "run-1"))


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


def test_invoke_maps_typed_sdk_exceptions_from_internal_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    cases = (
        (ExecutorValidationError("bad manifest"), astrid.CapabilityValidationError),
        (ValueError("missing required input(s): brief"), astrid.CapabilityInvocationError),
        (LeaseError("missing lease"), astrid.CapabilityLeaseError),
        (NotWriterError(session_id="S-1", writer_id="S-2"), astrid.CapabilityLeaseError),
        (StaleEpochError(expected=1, actual=2), astrid.CapabilityLeaseError),
        (StaleTailError(expected="sha256:abc", actual="sha256:def"), astrid.CapabilityEventLogError),
        (EventLogError("verification failed"), astrid.CapabilityEventLogError),
    )

    for internal_error, expected in cases:
        def fake_run_executor(request: Any, registry: Any, *, _internal_error=internal_error) -> Any:
            raise _internal_error

        monkeypatch.setattr(sdk, "run_executor", fake_run_executor)
        with pytest.raises(expected):
            astrid.invoke(
                "editorial.arrange",
                kind="executor",
                include_installed=False,
                out=tmp_path,
            )


def test_invoke_missing_input_runner_errors_raise_sdk_missing_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")

    def fake_run_executor(request: Any, registry: Any) -> Any:
        from astrid.core.executor.runner import ExecutorRunnerError

        raise ExecutorRunnerError("executor 'editorial.arrange' missing required input(s): brief")

    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    with pytest.raises(astrid.CapabilityMissingInputError, match="missing required input"):
        astrid.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
            out=tmp_path,
        )


def test_invoke_maps_executor_result_error_into_public_taxonomy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")

    def fake_run_executor(request: Any, registry: Any) -> _FakeExecutorResult:
        return _FakeExecutorResult(
            executor_id=request.executor_id,
            kind="built_in",
            command=("python", "-m", "astrid", "executors", "run", request.executor_id),
            cwd=Path("/tmp/executor"),
            env=MappingProxyType({}),
            payload=MappingProxyType({}),
            returncode=1,
            error=astrid.ExecError(
                code="in_process_precondition",
                type="precondition",
                message="wrong interpreter",
                recovery="use subprocess mode",
            ),
        )

    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    result = astrid.invoke(
        "editorial.arrange",
        kind="executor",
        include_installed=False,
        out=tmp_path,
    )

    assert result.ok is False
    assert result.error == {
        "code": "in_process_precondition",
        "type": "precondition",
        "message": "wrong interpreter",
        "recovery": "use subprocess mode",
        "sdk_error": "CapabilityPreconditionError",
        "sdk_category": "precondition",
    }


def test_invoke_maps_orchestrator_result_errors_into_public_taxonomy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")

    class _FailingOrchestratorResult(_FakeOrchestratorResult):
        def __init__(self) -> None:
            super().__init__()
            self.ok = False
            self.errors = (OrchestratorRunError(message="runtime exploded", kind="runtime"),)

        def to_dict(self) -> dict[str, Any]:
            payload = super().to_dict()
            payload["errors"] = [{"kind": "runtime", "message": "runtime exploded"}]
            payload["ok"] = False
            payload["returncode"] = 1
            return payload

    def fake_run_orchestrator(request: Any, registry: Any) -> _FailingOrchestratorResult:
        return _FailingOrchestratorResult()

    monkeypatch.setattr(sdk, "run_orchestrator", fake_run_orchestrator)

    result = astrid.invoke(
        "video_editing.hype",
        kind="orchestrator",
        include_installed=False,
        out=tmp_path,
    )

    assert result.ok is False
    assert result.error == {
        "kind": "runtime",
        "message": "runtime exploded",
        "sdk_error": "CapabilityRuntimeError",
        "sdk_category": "runtime",
    }
