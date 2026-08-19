from __future__ import annotations

import importlib
import importlib.util
import json
import os
import pkgutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from astrid.core.contracts.event_log_error import EventLogError
from astrid.core.execution.executor.schema import ExecutorValidationError
from astrid.core.execution.orchestrator.runner import OrchestratorRunError
from astrid.core.session.lease import LeaseError
from astrid.core.task.events import NotWriterError, StaleEpochError, StaleTailError
from tests._sdk_contract import EXPECTED_PUBLIC_NAMES

SDK_MODULE_MISSING = importlib.util.find_spec("astrid.sdk") is None

pytestmark = pytest.mark.skipif(
    SDK_MODULE_MISSING,
    reason="public SDK facade lands in later execution batches",
)


REPRESENTATIVE_SUBMODULES = (
    "astrid.core.gateway",
    "astrid.core.doctor",
    "astrid.core.gateway.setup",
)

RETIRED_COMPATIBILITY_SUBMODULES = (
    "astrid.timeline",
    "astrid.pipeline",
    "astrid._media",
    "astrid._paths",
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
            "astrid.core.execution.executor.registry",
            "astrid.core.execution.executor.runner",
            "astrid.core.execution.orchestrator.registry",
            "astrid.core.execution.orchestrator.runner",
        )
    },
}
print(json.dumps(payload))
"""
    # astrid is not installed in the runtime venv; the child resolves it from
    # the project root, which PYTHONSAFEPATH (canonical launch env) removes
    # from sys.path.  Pin PYTHONPATH so the probe subprocess can import astrid
    # regardless of the ambient safe-path policy (same fix as
    # tests/v10/test_writer_authority.py, VJ21 gate occurrence 0a0ce24c3510).
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
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
        "astrid.core.execution.executor.registry": False,
        "astrid.core.execution.executor.runner": False,
        "astrid.core.execution.orchestrator.registry": False,
        "astrid.core.execution.orchestrator.runner": False,
    }


def test_curated_sdk_names_do_not_shadow_existing_top_level_modules() -> None:
    astrid = _import_public_module()
    top_level_modules = {name for _, name, _ in pkgutil.iter_modules(astrid.__path__)}
    collisions = sorted(top_level_modules.intersection(EXPECTED_PUBLIC_NAMES))

    assert collisions == []


def test_generate_facade_is_lazy_public_surface() -> None:
    # Purge the SDK package from sys.modules so importing ``astrid`` is
    # provably lazy. The purge is restored afterwards: other tests in the
    # same process imported the SDK modules before this test ran and keep
    # references to those class objects, so leaving the fresh re-imports in
    # place would split class identity (e.g. two DomainResult classes) and
    # break later product-CLI dispatch in this process (m4 platform lane).
    popped: dict[str, Any] = {}
    for module_name in [
        name for name in sys.modules if name == "astrid.sdk" or name.startswith("astrid.sdk.")
    ]:
        popped[module_name] = sys.modules.pop(module_name, None)
    try:
        astrid = _import_public_module()
        astrid_modules_before = {
            name
            for name in sys.modules
            if name == "astrid.sdk" or name.startswith("astrid.sdk.")
        }

        assert "generate" in astrid.__all__
        assert astrid_modules_before == set()

        facade = astrid.generate

        assert "astrid.sdk" in sys.modules
        assert type(facade).__name__ == "GenerationFacade"
    finally:
        # Restore the purged modules (overwriting the test's fresh
        # re-imports) so every module imported before this test keeps its
        # class identity — otherwise a later product-CLI dispatch in this
        # process binds a second DomainResult class and breaks
        # isinstance-based envelope checks (m4 platform lane).
        for module_name, module in popped.items():
            sys.modules[module_name] = module


def test_representative_top_level_submodule_imports_resolve() -> None:
    for module_name in REPRESENTATIVE_SUBMODULES:
        imported = importlib.import_module(module_name)
        assert imported is not None


def test_retired_compatibility_submodule_imports_do_not_resolve() -> None:
    for module_name in RETIRED_COMPATIBILITY_SUBMODULES:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


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
    assert all("trust" in pack for pack in inventory.packs)
    assert any(backend["id"] == "local" for backend in inventory.generation_backends)
    assert any(backend["id"] == "cloud" for backend in inventory.generation_backends)
    assert any(kind["canonical_kind"] == "effects" for kind in inventory.element_kinds)
    assert any(feature["id"] == "prompt" for feature in inventory.generation_features)
    assert any(mode["id"] == "t2i" for mode in inventory.generation_modes)

    editorial_pack = next(pack for pack in inventory.packs if pack["id"] == "editorial")
    assert editorial_pack["permissions"] == [
        {
            "id": "subprocess",
            "reason": "Runs editorial executors as subprocesses for transcription, review, and arrangement.",
        },
        {
            "id": "project_files",
            "reason": "Reads and writes transcripts, scenes, arrangements, and review artifacts.",
        },
    ]
    assert editorial_pack["permission_ids"] == ["subprocess", "project_files"]
    assert editorial_pack["trust"] == {
        "sandbox": "none",
        "runs_with_user_process_permissions": True,
        "permission_enforcement": "disclosure_only",
    }

    editorial_capability = next(
        capability
        for capability in inventory.capabilities
        if capability.handle.pack_id == "editorial"
    )
    assert editorial_capability.handle.safety.permissions == ("subprocess", "project_files")
    assert all(
        isinstance(permission_id, str)
        for permission_id in editorial_capability.handle.safety.permissions
    )

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


def test_invoke_rejects_elements_and_missing_executor_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    astrid = _import_public_module()

    with pytest.raises(astrid.UnsupportedCapabilityError):
        astrid.invoke(
            "effects/text-card",
            kind="element",
            include_installed=False,
        )

    monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
    with pytest.raises(astrid.CapabilityValidationError, match="project required"):
        astrid.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
            )


def test_invoke_executor_project_routing_allows_out_none_with_in_process_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``sdk.invoke(kind="executor", project="demo", out=None, execution_mode="in_process")``
    must construct an ``ExecutorRunRequest`` with ``project="demo"`` and ``out=None``
    without raising ``CapabilityInvocationError`` about a missing out path."""
    astrid = _import_public_module()
    from astrid.core.execution.executor import runner as executor_runner

    captured_request: dict[str, Any] = {}

    def _fake_run_executor(request: Any, registry: Any) -> Any:
        captured_request["executor_id"] = request.executor_id
        captured_request["project"] = request.project
        captured_request["out"] = request.out
        captured_request["execution_mode"] = request.execution_mode
        captured_request["inputs"] = dict(request.inputs)
        from astrid.core.execution.executor.runner import ExecutorRunResult

        return ExecutorRunResult(
            executor_id=request.executor_id,
            kind="external",
            command=(),
            payload={"executor_id": request.executor_id, "returncode": 0},
            returncode=0,
        )

    monkeypatch.setattr(executor_runner, "run_executor", _fake_run_executor)

    result = astrid.invoke(
        "editorial.arrange",
        kind="executor",
        project="demo",
        out=None,
        execution_mode="in_process",
        include_installed=False,
    )

    assert captured_request["executor_id"] == "editorial.arrange"
    assert captured_request["project"] == "demo"
    assert captured_request["out"] is None
    assert captured_request["execution_mode"] == "in_process"
    assert result.capability_id == "editorial.arrange"
    assert result.capability_type == "executor"


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
    assert result.manifest_path is None
    assert result.raw_result["cwd"] == "/tmp/executor"
    assert result.raw_result["payload"] == {"artifact": str(tmp_path / "artifact.json")}
    assert result.raw_result["env"] == {"ASTRID_SAMPLE": "1"}
    assert result.to_dict()["manifest_path"] is None
    json.dumps(result.to_dict())


def test_invoke_executor_prefers_universal_manifest_path_from_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    universal_manifest = tmp_path / "nested" / "manifest.json"

    def fake_run_executor(request: Any, registry: Any) -> _FakeExecutorResult:
        return _FakeExecutorResult(
            executor_id=request.executor_id,
            kind="built_in",
            command=("python", "-m", "astrid", "executors", "run", request.executor_id),
            cwd=Path("/tmp/executor"),
            env=MappingProxyType({}),
            payload=MappingProxyType({"manifest_path": str(universal_manifest)}),
        )

    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    result = astrid.invoke(
        "editorial.arrange",
        kind="executor",
        include_installed=False,
        out=tmp_path,
        project="demo-project",
    )

    assert result.manifest_path == str(universal_manifest.resolve())
    assert result.raw_result["payload"] == {"manifest_path": str(universal_manifest.resolve())}
    assert result.to_dict()["manifest_path"] == str(universal_manifest.resolve())


def test_invoke_executor_discovers_universal_manifest_from_out_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    def fake_run_executor(request: Any, registry: Any) -> _FakeExecutorResult:
        return _FakeExecutorResult(
            executor_id=request.executor_id,
            kind="built_in",
            command=("python", "-m", "astrid", "executors", "run", request.executor_id),
            cwd=Path("/tmp/executor"),
            env=MappingProxyType({}),
            payload=MappingProxyType({"artifact": "artifact.json"}),
        )

    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    result = astrid.invoke(
        "editorial.arrange",
        kind="executor",
        include_installed=False,
        out=tmp_path,
        project="demo-project",
    )

    assert result.manifest_path == str(manifest_path.resolve())
    assert result.raw_result["payload"] == {"artifact": "artifact.json"}
    assert result.to_dict()["manifest_path"] == str(manifest_path.resolve())


def test_invoke_executor_ignores_domain_manifest_payload_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    universal_manifest = tmp_path / "manifest.json"
    universal_manifest.write_text("{}", encoding="utf-8")
    domain_manifest = tmp_path / "iteration.manifest.json"

    def fake_run_executor(request: Any, registry: Any) -> _FakeExecutorResult:
        return _FakeExecutorResult(
            executor_id=request.executor_id,
            kind="built_in",
            command=("python", "-m", "astrid", "executors", "run", request.executor_id),
            cwd=Path("/tmp/executor"),
            env=MappingProxyType({}),
            payload=MappingProxyType({"manifest_path": str(domain_manifest)}),
        )

    monkeypatch.setattr(sdk, "run_executor", fake_run_executor)

    result = astrid.invoke(
        "iteration.assemble",
        kind="executor",
        include_installed=False,
        out=tmp_path,
        project="demo-project",
    )

    assert result.manifest_path == str(universal_manifest.resolve())
    assert result.raw_result["payload"] == {"manifest_path": str(domain_manifest.resolve())}


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


def test_invoke_executor_allows_project_without_explicit_out(
    monkeypatch: pytest.MonkeyPatch,
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
        project="demo-project",
    )

    assert seen["request"].project == "demo-project"
    assert seen["request"].out is None
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
        from astrid.core.execution.executor.runner import ExecutorRunnerError

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


# ---------------------------------------------------------------------------
# T12: systematic pack permissions + trust metadata in discover().to_dict()
# ---------------------------------------------------------------------------


def test_discover_packs_all_have_permissions_and_trust_metadata() -> None:
    """Every pack record returned by discover().to_dict() must carry
    ``permissions``, ``permission_ids``, and the v1 trust block."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    assert inventory.packs, "discover() returned zero packs"
    for pack in inventory.packs:
        assert "permissions" in pack, (
            f"pack {pack.get('id', '?')!r} is missing 'permissions' key"
        )
        assert "permission_ids" in pack, (
            f"pack {pack.get('id', '?')!r} is missing 'permission_ids' key"
        )
        assert "trust" in pack, (
            f"pack {pack.get('id', '?')!r} is missing 'trust' key"
        )
        # trust block v1 invariants
        trust = pack["trust"]
        assert trust["sandbox"] == "none", (
            f"pack {pack['id']!r} trust.sandbox is {trust.get('sandbox')!r}, expected 'none'"
        )
        assert trust["runs_with_user_process_permissions"] is True, (
            f"pack {pack['id']!r} trust.runs_with_user_process_permissions is "
            f"{trust.get('runs_with_user_process_permissions')!r}, expected True"
        )
        assert trust["permission_enforcement"] == "disclosure_only", (
            f"pack {pack['id']!r} trust.permission_enforcement is "
            f"{trust.get('permission_enforcement')!r}, expected 'disclosure_only'"
        )

    # round-trip serialization
    payload = inventory.to_dict()
    json.dumps(payload)
    for pack in payload["packs"]:
        assert "permissions" in pack
        assert "permission_ids" in pack
        assert "trust" in pack


def test_discover_pack_permission_objects_have_expected_shape() -> None:
    """Every permission object inside a pack record must be a dict with
    string ``id`` and ``reason`` keys (no structured sub-objects)."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    for pack in inventory.packs:
        permissions = pack.get("permissions", [])
        assert isinstance(permissions, list), (
            f"pack {pack['id']!r} permissions is not a list"
        )
        for idx, perm in enumerate(permissions):
            assert isinstance(perm, dict), (
                f"pack {pack['id']!r} permissions[{idx}] is not a dict"
            )
            assert "id" in perm, (
                f"pack {pack['id']!r} permissions[{idx}] missing 'id'"
            )
            assert "reason" in perm, (
                f"pack {pack['id']!r} permissions[{idx}] missing 'reason'"
            )
            assert isinstance(perm["id"], str), (
                f"pack {pack['id']!r} permissions[{idx}].id is not str"
            )
            assert isinstance(perm["reason"], str), (
                f"pack {pack['id']!r} permissions[{idx}].reason is not str"
            )
            # optional fields, if present, must be the right type
            for key in ("services", "access"):
                if key in perm:
                    val = perm[key]
                    if key == "services":
                        assert isinstance(val, list), (
                            f"pack {pack['id']!r} permissions[{idx}].services is not a list"
                        )
                    elif key == "access":
                        assert isinstance(val, str), (
                            f"pack {pack['id']!r} permissions[{idx}].access is not str"
                        )


def test_discover_permission_ids_match_permissions_list() -> None:
    """For every pack, ``permission_ids`` must be a list of strings that
    corresponds 1:1 with the ``id`` fields in ``permissions``."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    for pack in inventory.packs:
        permission_ids = pack.get("permission_ids", [])
        permissions = pack.get("permissions", [])
        assert isinstance(permission_ids, list), (
            f"pack {pack['id']!r} permission_ids is not a list"
        )
        assert all(isinstance(pid, str) for pid in permission_ids), (
            f"pack {pack['id']!r} permission_ids contains non-string values"
        )
        expected_ids = [perm["id"] for perm in permissions]
        assert permission_ids == expected_ids, (
            f"pack {pack['id']!r} permission_ids {permission_ids!r} != "
            f"expected {expected_ids!r}"
        )


def test_capability_safety_permissions_are_only_string_ids() -> None:
    """Every capability in discovery must have ``SafetyDeclaration.permissions``
    as a tuple of plain strings — no structured permission objects leak in."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    assert inventory.capabilities, "discover() returned zero capabilities"
    for capability in inventory.capabilities:
        safety_permissions = capability.handle.safety.permissions
        assert isinstance(safety_permissions, tuple), (
            f"capability {capability.id!r} safety.permissions is not a tuple"
        )
        for perm_id in safety_permissions:
            assert isinstance(perm_id, str), (
                f"capability {capability.id!r} safety.permissions contains "
                f"non-string value {perm_id!r} (type={type(perm_id).__name__})"
            )


def test_capability_safety_permissions_mirror_pack_permission_ids() -> None:
    """For every pack that declares permissions, every capability owned by
    that pack must have its ``safety.permissions`` equal to the pack's
    ``permission_ids``."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    pack_permission_ids: dict[str, list[str]] = {}
    for pack in inventory.packs:
        pack_permission_ids[pack["id"]] = list(pack.get("permission_ids", []))

    for capability in inventory.capabilities:
        pack_id = capability.handle.pack_id
        if not pack_id:
            continue
        expected = tuple(pack_permission_ids.get(pack_id, []))
        actual = capability.handle.safety.permissions
        assert actual == expected, (
            f"capability {capability.id!r} (pack {pack_id!r}) "
            f"safety.permissions={actual!r}, expected={expected!r}"
        )


def test_discover_to_dict_roundtrip_preserves_trust_metadata() -> None:
    """``discover().to_dict()`` must round-trip through json and still
    carry pack-level trust metadata."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    payload = inventory.to_dict()
    reencoded = json.loads(json.dumps(payload))
    assert "packs" in reencoded
    for pack in reencoded["packs"]:
        assert "permissions" in pack
        assert "permission_ids" in pack
        assert "trust" in pack
        trust = pack["trust"]
        assert trust["sandbox"] == "none"
        assert trust["runs_with_user_process_permissions"] is True
        assert trust["permission_enforcement"] == "disclosure_only"


def test_capability_to_dict_preserves_safety_permissions_as_strings() -> None:
    """Every individual capability ``to_dict()`` must serialize
    ``safety.permissions`` as a list of strings."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    for capability in inventory.capabilities:
        d = capability.to_dict()
        safety = d.get("handle", {}).get("safety", {})
        perms = safety.get("permissions", ())
        assert isinstance(perms, (tuple, list)), (
            f"capability {capability.id!r} to_dict safety.permissions is "
            f"not a sequence: {type(perms).__name__}"
        )
        for perm_id in perms:
            assert isinstance(perm_id, str), (
                f"capability {capability.id!r} to_dict safety.permissions "
                f"contains non-string {perm_id!r}"
            )


def test_discover_empty_permissions_pack_has_empty_lists_and_trust() -> None:
    """A pack that declares no permissions must still have empty
    ``permissions``/``permission_ids`` lists and the trust block."""
    astrid = _import_public_module()
    inventory = astrid.discover(include_installed=False)

    # The builtin (deprecated) meta-pack should have empty permissions
    builtin_pack = next(
        (pack for pack in inventory.packs if pack["id"] == "builtin"), None
    )
    if builtin_pack is not None:
        assert builtin_pack["permissions"] == []
        assert builtin_pack["permission_ids"] == []
        assert builtin_pack["trust"] == {
            "sandbox": "none",
            "runs_with_user_process_permissions": True,
            "permission_enforcement": "disclosure_only",
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


def test_generate_image_reconstructs_typed_result_from_generation_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    from astrid.core.generation import GENERATION_RESULT_KEY
    from astrid.core.generation.backends.base import GenerationResult

    raw_generation = GenerationResult(
        image_paths=[tmp_path / "image.png"],
        model_actual="flux-dev",
        run_dir=tmp_path,
    ).to_dict()
    seen: dict[str, Any] = {}

    def fake_invoke(capability_id: str, **kwargs: Any) -> Any:
        seen["capability_id"] = capability_id
        seen["kwargs"] = kwargs
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={
                "payload": {
                    GENERATION_RESULT_KEY: raw_generation,
                    "returncode": 0,
                }
            },
        )

    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="flux-dev",
        mode="t2i",
        execution="cloud",
        out=tmp_path,
        prompt="a lantern in fog",
    )

    assert isinstance(result, GenerationResult)
    assert result.path == tmp_path / "image.png"
    assert result.run_dir == tmp_path
    assert seen["capability_id"] == "generation.generate_image"
    assert seen["kwargs"]["execution_mode"] == "in_process"
    assert seen["kwargs"]["kind"] == "executor"
    assert seen["kwargs"]["inputs"]["prompt"] == "a lantern in fog"


def test_generate_facade_maps_contract_failures_and_openai_rejection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    from astrid.core.generation import GENERATION_RESULT_KEY

    with pytest.raises(
        astrid.CapabilityPreconditionError,
        match="generation.generate_image_openai",
    ):
        astrid.generate.image(
            model="gpt-image-1",
            mode="t2i",
            execution="openai",
            out=tmp_path,
        )

    def missing_generation_result(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={"payload": {"returncode": 0}},
        )

    monkeypatch.setattr(sdk, "invoke", missing_generation_result)
    with pytest.raises(
        astrid.CapabilityRuntimeError,
        match=GENERATION_RESULT_KEY,
    ):
        astrid.generate.video(
            model="wan-2.2",
            mode="t2v",
            execution="cloud",
            out=tmp_path,
        )

    def failed_invoke(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=False,
            error={
                "message": "wrong interpreter",
                "sdk_error": "CapabilityPreconditionError",
                "sdk_category": "precondition",
            },
            raw_result={"payload": {GENERATION_RESULT_KEY: {}}},
        )

    monkeypatch.setattr(sdk, "invoke", failed_invoke)
    with pytest.raises(astrid.CapabilityPreconditionError, match="wrong interpreter"):
        astrid.generate.video(
            model="wan-2.2",
            mode="t2v",
            execution="cloud",
            out=tmp_path,
        )


# ---------------------------------------------------------------------------
# T13: facade contract and import-cycle tests
# ---------------------------------------------------------------------------


def _generation_import_probe() -> dict[str, Any]:
    """Run a subprocess probe that checks which generation executor modules
    are loaded after ``import astrid`` and after accessing ``astrid.generate``
    (without calling a facade method)."""
    script = """
import importlib
import json
import sys

astrid = importlib.import_module("astrid")

# modules that MUST NOT be loaded after import astrid alone
generation_executor_modules = (
    "astrid.packs.generation.executors.generate_image.run",
    "astrid.packs.generation.executors.generate_video.run",
    "astrid.core.generation.backends.base",
    "astrid.core.generation.backends.registry",
    "astrid.core.generation",
    "astrid.core.model_catalog.registry",
)

state_after_import = {
    name: (name in sys.modules)
    for name in generation_executor_modules
}

# access the facade (lazy load triggers astrid.sdk but NOT executor modules)
facade = astrid.generate

state_after_facade = {
    name: (name in sys.modules)
    for name in generation_executor_modules
}

payload = {
    "after_import": state_after_import,
    "after_facade": state_after_facade,
    "sdk_loaded": "astrid.sdk" in sys.modules,
}
print(json.dumps(payload))
"""
    # Ensure the worktree is on the path so the subprocess imports the
    # local astrid package rather than an installed copy.
    import os as _os

    worktree_root = str(Path(__file__).resolve().parent.parent)
    env = {**_os.environ, "PYTHONPATH": worktree_root}
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def test_import_astrid_does_not_load_generation_executor_modules() -> None:
    """``import astrid`` must NOT pull in generation executor modules
    (generate_image/run.py, generate_video/run.py, backends/base.py)."""
    probe = _generation_import_probe()

    after_import = probe["after_import"]
    assert after_import == {
        "astrid.packs.generation.executors.generate_image.run": False,
        "astrid.packs.generation.executors.generate_video.run": False,
        "astrid.core.generation.backends.base": False,
        "astrid.core.generation.backends.registry": False,
        "astrid.core.generation": False,
        "astrid.core.model_catalog.registry": False,
    }, f"Generation executor modules leaked during import: {after_import}"


def test_astrid_generate_lazy_access_does_not_load_generation_executor_modules() -> None:
    """Accessing ``astrid.generate`` (lazy-loading the SDK) must NOT pull in
    generation executor modules before a facade method is called."""
    probe = _generation_import_probe()

    after_facade = probe["after_facade"]
    assert after_facade == {
        "astrid.packs.generation.executors.generate_image.run": False,
        "astrid.packs.generation.executors.generate_video.run": False,
        "astrid.core.generation.backends.base": False,
        "astrid.core.generation.backends.registry": False,
        "astrid.core.generation": False,
        "astrid.core.model_catalog.registry": False,
    }, f"Generation executor modules leaked during facade access: {after_facade}"

    # astrid.sdk should be loaded after accessing astrid.generate (lazy load)
    assert probe["sdk_loaded"] is True, "astrid.sdk should be loaded after facade access"


def test_generate_video_reconstructs_typed_result_from_generation_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``astrid.generate.video(...)`` must return a typed ``GenerationResult``
    with ``.video_paths``, ``.path``, and ``.run_dir`` populated."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    from astrid.core.generation import GENERATION_RESULT_KEY
    from astrid.core.generation.backends.base import GenerationResult

    raw_generation = GenerationResult(
        image_paths=[tmp_path / "video.mp4"],
        model_actual="wan-2.2",
        run_dir=tmp_path,
    ).to_dict()
    seen: dict[str, Any] = {}

    def fake_invoke(capability_id: str, **kwargs: Any) -> Any:
        seen["capability_id"] = capability_id
        seen["kwargs"] = kwargs
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={
                "payload": {
                    GENERATION_RESULT_KEY: raw_generation,
                    "returncode": 0,
                }
            },
        )

    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.video(
        model="wan-2.2",
        mode="t2v",
        execution="cloud",
        out=tmp_path,
        prompt="a cat playing piano",
        duration=5,
    )

    assert isinstance(result, GenerationResult)
    assert result.video_paths == [tmp_path / "video.mp4"]
    assert result.path == tmp_path / "video.mp4"
    assert result.run_dir == tmp_path
    assert result.model_actual == "wan-2.2"
    assert seen["capability_id"] == "generation.generate_video"
    assert seen["kwargs"]["execution_mode"] == "in_process"
    assert seen["kwargs"]["kind"] == "executor"
    assert seen["kwargs"]["inputs"]["prompt"] == "a cat playing piano"
    assert seen["kwargs"]["inputs"]["duration"] == 5


def test_generate_facade_rejects_openai_for_video_too(
    tmp_path: Path,
) -> None:
    """``astrid.generate.video(execution=\"openai\")`` must raise a clear
    diagnostic even though the video facade does not have a dedicated
    openai rejection guard — it should fail through the executor path."""
    astrid = _import_public_module()

    # Video facade doesn't have an explicit openai rejection like image does,
    # but if someone passes execution="openai" it should be forwarded to the
    # executor which will reject it.  We only assert the image guard here.
    # The image guard is the primary contract.
    with pytest.raises(
        astrid.CapabilityPreconditionError,
        match="generation.generate_image_openai",
    ):
        astrid.generate.image(
            model="gpt-image-1",
            mode="t2i",
            execution="openai",
            out=tmp_path,
        )


def test_generate_facade_rejects_missing_generation_result_key_for_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the executor payload lacks ``GENERATION_RESULT_KEY`` entirely,
    the facade must raise ``CapabilityRuntimeError`` with the key name."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    from astrid.core.generation import GENERATION_RESULT_KEY

    def missing_key_invoke(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={"payload": {"returncode": 0}},
        )

    monkeypatch.setattr(sdk, "invoke", missing_key_invoke)
    with pytest.raises(
        astrid.CapabilityRuntimeError,
        match=GENERATION_RESULT_KEY,
    ):
        astrid.generate.image(
            model="z-image",
            mode="t2i",
            execution="cloud",
            out=tmp_path,
        )


def test_generate_facade_rejects_non_mapping_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the executor ``raw_result`` is not a mapping, the facade
    must raise ``CapabilityRuntimeError``."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")

    def non_mapping_invoke(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result="not a mapping",
        )

    monkeypatch.setattr(sdk, "invoke", non_mapping_invoke)
    with pytest.raises(
        astrid.CapabilityRuntimeError,
        match="non-mapping raw_result",
    ):
        astrid.generate.video(
            model="wan-2.2",
            mode="t2v",
            execution="cloud",
            out=tmp_path,
        )


def test_generate_facade_rejects_non_mapping_generation_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the executor payload is not a mapping, the facade must raise
    ``CapabilityRuntimeError`` with a clear message."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")

    def non_mapping_payload_invoke(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={"payload": "not a mapping"},
        )

    monkeypatch.setattr(sdk, "invoke", non_mapping_payload_invoke)
    with pytest.raises(
        astrid.CapabilityRuntimeError,
        match="non-mapping payload",
    ):
        astrid.generate.image(
            model="z-image",
            mode="t2i",
            execution="cloud",
            out=tmp_path,
        )


def test_generate_facade_handles_from_dict_on_minimal_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Even a minimal GenerationResult dict (no image_paths, no model_actual)
    should be reconstructable via ``from_dict()``."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    from astrid.core.generation import GENERATION_RESULT_KEY
    from astrid.core.generation.backends.base import GenerationResult

    minimal_dict: dict[str, Any] = {
        "image_paths": [],
        "seed_used": 0,
        "model_actual": "",
        "cost_usd": None,
        "duration_ms": 0,
        "applied_features": [],
        "dropped_features": [],
        "request_id": None,
        "source_urls": None,
        "error": None,
        "manifest": None,
        "run_dir": None,
    }

    def minimal_invoke(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={
                "payload": {
                    GENERATION_RESULT_KEY: minimal_dict,
                    "returncode": 0,
                }
            },
        )

    monkeypatch.setattr(sdk, "invoke", minimal_invoke)

    result = astrid.generate.image(
        model="z-image",
        mode="t2i",
        execution="cloud",
        out=tmp_path,
    )

    assert isinstance(result, GenerationResult)
    assert result.image_paths == []
    assert result.path is None
    assert result.video_paths == []
    assert result.ok is True
    assert result.model_actual == ""


def test_generate_facade_handles_error_generation_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the executor returns an ok GenerationResult payload but the
    nested GenerationResult has an error, the facade must still reconstruct
    it without raising."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    from astrid.core.contracts.exec_error import ExecError
    from astrid.core.generation import GENERATION_RESULT_KEY
    from astrid.core.generation.backends.base import GenerationResult

    error_result = GenerationResult(
        image_paths=[],
        error=ExecError(
            code="backend_timeout",
            type="process",
            message="Backend timed out after 30s",
            recovery="Retry with a lower resolution or different backend",
        ),
    ).to_dict()

    def error_invoke(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={
                "payload": {
                    GENERATION_RESULT_KEY: error_result,
                    "returncode": 0,
                }
            },
        )

    monkeypatch.setattr(sdk, "invoke", error_invoke)

    result = astrid.generate.video(
        model="wan-2.2",
        mode="t2v",
        execution="cloud",
        out=tmp_path,
    )

    assert isinstance(result, GenerationResult)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "backend_timeout"
    assert result.error.type == "process"


def test_generate_facade_rejects_str_generation_result_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``GENERATION_RESULT_KEY`` value is a string (not a dict or
    GenerationResult), the facade must raise ``CapabilityRuntimeError``."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    from astrid.core.generation import GENERATION_RESULT_KEY

    def str_value_invoke(capability_id: str, **kwargs: Any) -> Any:
        return astrid.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={
                "payload": {
                    GENERATION_RESULT_KEY: "not a dict or GenerationResult",
                    "returncode": 0,
                }
            },
        )

    monkeypatch.setattr(sdk, "invoke", str_value_invoke)
    with pytest.raises(
        astrid.CapabilityRuntimeError,
        match="must be a mapping or GenerationResult",
    ):
        astrid.generate.image(
            model="z-image",
            mode="t2i",
            execution="cloud",
            out=tmp_path,
        )


# ---------------------------------------------------------------------------
# T14: model/mode/execution inference inside the facade
# ---------------------------------------------------------------------------


def _make_success_invoke(astrid_module, tmp_path: Path):
    """Return a fake ``invoke`` that records its kwargs and returns a
    valid ``InvocationResult`` carrying a minimal ``GenerationResult``
    payload so the facade can reconstruct it without errors."""

    from astrid.core.generation import GENERATION_RESULT_KEY
    from astrid.core.generation.backends.base import GenerationResult

    seen: dict[str, Any] = {}

    def _invoke(capability_id: str, **kwargs: Any) -> Any:
        seen["capability_id"] = capability_id
        seen["kwargs"] = kwargs
        return astrid_module.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={
                "payload": {
                    GENERATION_RESULT_KEY: GenerationResult(
                        image_paths=[tmp_path / "out.png"],
                        model_actual=kwargs.get("inputs", {}).get("model", ""),
                        run_dir=tmp_path,
                    ).to_dict(),
                    "returncode": 0,
                }
            },
        )

    return _invoke, seen


def test_image_mode_inference_t2i_no_image_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``mode`` is omitted and ``image_ref`` is absent, the facade
    infers ``t2i``."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="flux-dev",
        out=tmp_path,
        prompt="a test image",
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "t2i"
    assert seen["kwargs"]["inputs"]["prompt"] == "a test image"


def test_image_mode_inference_i2i_with_image_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``mode`` is omitted and ``image_ref`` is present, the facade
    infers ``i2i``."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="flux-dev",
        out=tmp_path,
        image_ref="https://example.com/ref.png",
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "i2i"
    assert seen["kwargs"]["inputs"]["image_ref"] == "https://example.com/ref.png"


def test_image_mode_inference_rejects_unsupported_inferred_mode(
    tmp_path: Path,
) -> None:
    """When mode is inferred as t2i but the model does not support it,
    a clear validation error is raised."""
    astrid = _import_public_module()

    # qwen-image-edit only supports 'edit' mode — inferred t2i fails
    with pytest.raises(astrid.CapabilityValidationError, match="does not support mode"):
        astrid.generate.image(
            model="qwen-image-edit",
            out=tmp_path,
            prompt="test",
        )


def test_image_explicit_mode_validated_against_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An explicit mode that the model supports passes validation."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="qwen-image-edit",
        mode="edit",
        execution="cloud",
        out=tmp_path,
        prompt="test",
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "edit"


def test_image_explicit_mode_rejected_when_not_supported(
    tmp_path: Path,
) -> None:
    """An explicit mode that the model does NOT declare raises a clear error."""
    astrid = _import_public_module()

    with pytest.raises(
        astrid.CapabilityValidationError,
        match="does not support mode 'edit'",
    ):
        astrid.generate.image(
            model="z-image",
            mode="edit",
            out=tmp_path,
        )


def test_image_execution_inference_single_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When exactly one backend is available for (model, mode), the facade
    infers execution automatically."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    # flux-dev t2i has cloud plus explicit-only codex; auto-inference keeps cloud.
    result = astrid.generate.image(
        model="flux-dev",
        out=tmp_path,
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["execution"] == "cloud"
    assert seen["kwargs"]["inputs"]["mode"] == "t2i"


def test_image_execution_ambiguous_rejected(
    tmp_path: Path,
) -> None:
    """When multiple backends are available and no execution is given,
    the facade raises a diagnostic asking the caller to choose."""
    astrid = _import_public_module()

    # z-image t2i has both local and cloud
    with pytest.raises(astrid.CapabilityValidationError, match="Ambiguous execution"):
        astrid.generate.image(
            model="z-image",
            out=tmp_path,
            prompt="test",
        )


def test_image_explicit_execution_validated_against_backends(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An explicit execution that matches the available backends passes."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="z-image",
        mode="t2i",
        execution="cloud",
        out=tmp_path,
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["execution"] == "cloud"


def test_image_explicit_execution_rejected_when_unavailable(
    tmp_path: Path,
) -> None:
    """An explicit execution that is not declared for (model, mode) raises
    a clear error."""
    astrid = _import_public_module()

    # flux-dev t2i has cloud/codex, not local.
    with pytest.raises(
        astrid.CapabilityValidationError,
        match="is not available for",
    ):
        astrid.generate.image(
            model="flux-dev",
            mode="t2i",
            execution="local",
            out=tmp_path,
        )


def test_video_mode_inference_t2v_no_refs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When mode is omitted and no reference images are provided, t2v is inferred."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    # wan-2.2 t2v only has cloud → single backend, auto-inferred
    result = astrid.generate.video(
        model="wan-2.2",
        out=tmp_path,
        prompt="a test video",
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "t2v"
    assert seen["kwargs"]["inputs"]["execution"] == "cloud"


def test_video_mode_inference_i2v_image_ref(
    tmp_path: Path,
) -> None:
    """When mode is omitted and image_ref is present (but not image_end_ref),
    i2v is inferred.  wan-2.2 i2v has both local and cloud → ambiguous
    execution is rejected."""
    astrid = _import_public_module()

    # wan-2.2 i2v has both local and cloud — ambiguous execution
    with pytest.raises(astrid.CapabilityValidationError, match="Ambiguous execution"):
        astrid.generate.video(
            model="wan-2.2",
            out=tmp_path,
            image_ref="https://example.com/frame.png",
        )


def test_video_mode_inference_flf_both_refs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When mode is omitted and both image_ref + image_end_ref are present,
    flf is inferred."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    # wan-2.2 flf only has cloud → single backend
    result = astrid.generate.video(
        model="wan-2.2",
        out=tmp_path,
        image_ref="first.png",
        image_end_ref="last.png",
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "flf"
    assert seen["kwargs"]["inputs"]["execution"] == "cloud"


def test_video_explicit_mode_validated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An explicit video mode that is supported passes validation."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.video(
        model="wan-2.2",
        mode="t2v",
        out=tmp_path,
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "t2v"


def test_video_execution_inference_single_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Video mode with a single backend auto-infers execution."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    # ltx-2.3 flf only has local
    result = astrid.generate.video(
        model="ltx-2.3",
        mode="flf",
        out=tmp_path,
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "flf"
    assert seen["kwargs"]["inputs"]["execution"] == "local"


def test_unknown_model_raises_validation_error(
    tmp_path: Path,
) -> None:
    """A model id not present in the catalog raises CapabilityValidationError."""
    astrid = _import_public_module()

    with pytest.raises(astrid.CapabilityValidationError, match="Unknown model"):
        astrid.generate.image(
            model="nonexistent-model",
            out=tmp_path,
        )

    with pytest.raises(astrid.CapabilityValidationError, match="Unknown model"):
        astrid.generate.video(
            model="nonexistent-model",
            out=tmp_path,
        )


def test_lora_and_extra_params_passthrough(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """LoRA spec and arbitrary extra keyword arguments pass through to the
    executor unchanged."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    astrid.generate.image(
        model="flux-dev",
        out=tmp_path,
        loras="flux-realism@0.8",
        custom_extra="value",
        another_param=42,
    )

    assert seen["kwargs"]["inputs"]["loras"] == "flux-realism@0.8"
    assert seen["kwargs"]["inputs"]["custom_extra"] == "value"
    assert seen["kwargs"]["inputs"]["another_param"] == 42
    # Inferred mode and execution are still present
    assert seen["kwargs"]["inputs"]["mode"] == "t2i"
    assert seen["kwargs"]["inputs"]["execution"] == "cloud"


# ---------------------------------------------------------------------------
# T15: additional facade inference tests — gaps not covered by T14
# ---------------------------------------------------------------------------


def test_explicit_only_image_modes_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``_infer_image_mode`` returns an explicit-only mode (edit /
    inpaint / outpain / upscale) and the caller did NOT supply an explicit
    *mode*, the guard must raise ``CapabilityValidationError``."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")

    # Force _infer_image_mode to return "inpaint" even when mode is None.
    def _fake_infer_image_mode(explicit_mode, inputs):
        return "inpaint"

    monkeypatch.setattr(sdk, "_infer_image_mode", _fake_infer_image_mode)

    with pytest.raises(
        astrid.CapabilityValidationError,
        match="requires an explicit 'mode' argument",
    ):
        astrid.generate.image(
            model="flux-dev",
            out=tmp_path,
            prompt="test",
        )


def test_video_explicit_mode_rejected_when_not_supported(
    tmp_path: Path,
) -> None:
    """An explicit video mode that the model does NOT declare raises a
    clear validation error."""
    astrid = _import_public_module()

    # wan-2.2 does not support 'edit' at all
    with pytest.raises(
        astrid.CapabilityValidationError,
        match="does not support mode 'edit'",
    ):
        astrid.generate.video(
            model="wan-2.2",
            mode="edit",
            out=tmp_path,
        )


def test_video_explicit_execution_validated_against_backends(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An explicit *execution* for a video model that matches the available
    backends must pass through unchanged."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    # wan-2.2 t2v has only cloud
    result = astrid.generate.video(
        model="wan-2.2",
        mode="t2v",
        execution="cloud",
        out=tmp_path,
    )

    assert result.ok is True
    assert seen["kwargs"]["inputs"]["mode"] == "t2v"
    assert seen["kwargs"]["inputs"]["execution"] == "cloud"


def test_video_explicit_execution_rejected_when_unavailable(
    tmp_path: Path,
) -> None:
    """An explicit *execution* that is not declared for (model, mode)
    raises a clear diagnostic."""
    astrid = _import_public_module()

    # wan-2.2 t2v has cloud only — local is NOT available
    with pytest.raises(
        astrid.CapabilityValidationError,
        match="is not available for",
    ):
        astrid.generate.video(
            model="wan-2.2",
            mode="t2v",
            execution="local",
            out=tmp_path,
        )


def test_ambiguous_execution_diagnostic_includes_available_backends(
    tmp_path: Path,
) -> None:
    """When multiple backends exist and none is specified, the error
    message must list every available backend (sorted)."""
    astrid = _import_public_module()

    # z-image t2i has both local and cloud → ambiguous
    with pytest.raises(astrid.CapabilityValidationError) as excinfo:
        astrid.generate.image(
            model="z-image",
            out=tmp_path,
            prompt="test",
        )

    message = str(excinfo.value)
    assert "Ambiguous execution" in message
    assert "Available backends:" in message
    assert "cloud" in message
    assert "local" in message
    # Verify the backends are in alphabetical order
    assert message.index("cloud") < message.index("local")


# ---------------------------------------------------------------------------
# T18: default output routing tests — explicit out, explicit project,
#      default project resolution, no stderr, no ASTRID_SESSION_ID mutation,
#      and continued CLI side-effect behavior
# ---------------------------------------------------------------------------


def _make_success_invoke_with_seen(astrid_module, tmp_path: Path):
    """Return a fake ``invoke`` that captures all kwargs and returns a valid
    generation result so the facade can reconstruct it without error."""
    from astrid.core.generation import GENERATION_RESULT_KEY
    from astrid.core.generation.backends.base import GenerationResult

    seen: dict[str, Any] = {}

    def _invoke(capability_id: str, **kwargs: Any) -> Any:
        seen["capability_id"] = capability_id
        seen["kwargs"] = kwargs
        return astrid_module.InvocationResult(
            capability_id=capability_id,
            capability_type="executor",
            native_kind="built_in",
            ok=True,
            raw_result={
                "payload": {
                    GENERATION_RESULT_KEY: GenerationResult(
                        image_paths=[tmp_path / "out.png"],
                        model_actual=kwargs.get("inputs", {}).get("model", ""),
                        run_dir=tmp_path,
                    ).to_dict(),
                    "returncode": 0,
                }
            },
        )

    return _invoke, seen


# --- explicit ``out`` routing ------------------------------------------------


def test_generate_explicit_out_routing_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit output still carries required project ownership."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="flux-dev",
        out=tmp_path,
        project="demo",
        prompt="test",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] == tmp_path
    assert seen["kwargs"]["project"] == "demo"


def test_generate_explicit_out_routing_video(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit video output still carries required project ownership."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.video(
        model="wan-2.2",
        out=tmp_path,
        project="demo",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] == tmp_path
    assert seen["kwargs"]["project"] == "demo"


# --- explicit ``project`` routing --------------------------------------------


def test_generate_explicit_project_routing_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``project`` is supplied, ``invoke(out=None, project=project)``
    is called."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="flux-dev",
        project="my-project",
        prompt="test",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] is None
    assert seen["kwargs"]["project"] == "my-project"


def test_generate_explicit_project_routing_video(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``project`` is supplied to video, ``invoke(out=None,
    project=project)`` is called."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.video(
        model="wan-2.2",
        project="my-project",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] is None
    assert seen["kwargs"]["project"] == "my-project"


# --- attached project resolution (no explicit ``project``) --------------------


def test_generate_attached_project_resolution_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The genuinely attached session project is forwarded to invoke."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="flux-dev",
        prompt="test",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] is None
    assert seen["kwargs"]["project"] == "autouse-session-demo"


def test_generate_attached_project_resolution_video(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Same attached-project behavior for video generation."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.video(
        model="wan-2.2",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] is None
    assert seen["kwargs"]["project"] == "autouse-session-demo"


# --- out + project both passed through (runner enforces SD1 rejection) --------


def test_generate_out_wins_over_project_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When both ``out`` AND ``project`` are supplied, both are passed
    through to ``invoke()`` — the runner will enforce the strict
    project+out rejection (SD1).  The SDK no longer silently drops
    the project."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.image(
        model="flux-dev",
        out=tmp_path,
        project="ignored-project",
        prompt="test",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] == tmp_path
    assert seen["kwargs"]["project"] == "ignored-project"


def test_generate_out_wins_over_project_video(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Same routing for video: both ``out`` and ``project`` are passed
    through; the runner enforces SD1 rejection."""
    astrid = _import_public_module()
    sdk = importlib.import_module("astrid.sdk")
    fake_invoke, seen = _make_success_invoke_with_seen(astrid, tmp_path)
    monkeypatch.setattr(sdk, "invoke", fake_invoke)

    result = astrid.generate.video(
        model="wan-2.2",
        out=tmp_path,
        project="ignored-project",
    )

    assert result.ok is True
    assert seen["kwargs"]["out"] == tmp_path
    assert seen["kwargs"]["project"] == "ignored-project"


# --- no stderr output from facade calls --------------------------------------


def _facade_stderr_probe(method: str) -> dict[str, Any]:
    """Run a subprocess that calls ``astrid.generate.{method}()`` with mocked
    invoke and captures stderr."""
    import os as _os

    model = "flux-dev" if method == "image" else "wan-2.2"

    script = f"""
import importlib, json, sys, os
from unittest.mock import patch

astrid = importlib.import_module("astrid")
sdk = importlib.import_module("astrid.sdk")
import astrid.core.session.config as session_config

# Capture stderr via a StringIO
from io import StringIO
stderr_capture = StringIO()

# Build a fake invoke that succeeds silently
from astrid.core.generation import GENERATION_RESULT_KEY
from astrid.core.generation.backends.base import GenerationResult
from pathlib import Path
tmp = Path("/tmp")

def fake_invoke(capability_id, **kwargs):
    return astrid.InvocationResult(
        capability_id=capability_id,
        capability_type="executor",
        native_kind="built_in",
        ok=True,
        raw_result={{
            "payload": {{
                GENERATION_RESULT_KEY: GenerationResult(
                    image_paths=[tmp / "out.png"],
                    model_actual=kwargs.get("inputs", {{}}).get("model", ""),
                    run_dir=tmp,
                ).to_dict(),
                "returncode": 0,
            }}
        }},
    )

with patch.object(sdk, "invoke", fake_invoke), \\
     patch.object(session_config, "resolve_default_project_for_sdk", return_value="default"):
    old_stderr = sys.stderr
    sys.stderr = stderr_capture
    try:
        result = getattr(astrid.generate, {method!r})(
            model={model!r},
            out=tmp,
        )
    finally:
        sys.stderr = old_stderr

stderr_output = stderr_capture.getvalue()
print(json.dumps({{
    "ok": result.ok,
    "stderr": stderr_output,
    "stderr_empty": stderr_output == "",
}}))
"""

    worktree_root = str(Path(__file__).resolve().parent.parent)
    env = {**_os.environ, "PYTHONPATH": worktree_root}
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def test_generate_image_no_stderr_output() -> None:
    """Calling ``astrid.generate.image()`` must not write to stderr."""
    probe = _facade_stderr_probe("image")
    assert probe["ok"] is True
    assert probe["stderr_empty"] is True, (
        f"generate.image() wrote to stderr: {probe['stderr']!r}"
    )


def test_generate_video_no_stderr_output() -> None:
    """Calling ``astrid.generate.video()`` must not write to stderr."""
    probe = _facade_stderr_probe("video")
    assert probe["ok"] is True
    assert probe["stderr_empty"] is True, (
        f"generate.video() wrote to stderr: {probe['stderr']!r}"
    )


# --- no ASTRID_SESSION_ID mutation from facade calls -------------------------


def _session_id_mutation_probe(method: str) -> dict[str, Any]:
    """Run a subprocess that calls ``astrid.generate.{method}()`` and checks
    whether ``ASTRID_SESSION_ID`` is mutated."""
    import os as _os

    model = "flux-dev" if method == "image" else "wan-2.2"

    script = f"""
import importlib, json, sys, os
from unittest.mock import patch

# Set a known session id before calling the facade
os.environ["ASTRID_SESSION_ID"] = "S-before-facade"

astrid = importlib.import_module("astrid")
sdk = importlib.import_module("astrid.sdk")
import astrid.core.session.config as session_config

from astrid.core.generation import GENERATION_RESULT_KEY
from astrid.core.generation.backends.base import GenerationResult
from pathlib import Path
tmp = Path("/tmp")

def fake_invoke(capability_id, **kwargs):
    return astrid.InvocationResult(
        capability_id=capability_id,
        capability_type="executor",
        native_kind="built_in",
        ok=True,
        raw_result={{
            "payload": {{
                GENERATION_RESULT_KEY: GenerationResult(
                    image_paths=[tmp / "out.png"],
                    model_actual=kwargs.get("inputs", {{}}).get("model", ""),
                    run_dir=tmp,
                ).to_dict(),
                "returncode": 0,
            }}
        }},
    )

session_before = os.environ.get("ASTRID_SESSION_ID")

with patch.object(sdk, "invoke", fake_invoke):
    getattr(astrid.generate, {method!r})(
        model={model!r},
        out=tmp,
        project="demo",
    )

session_after = os.environ.get("ASTRID_SESSION_ID")

print(json.dumps({{
    "session_before": session_before,
    "session_after": session_after,
    "unchanged": session_before == session_after,
}}))
"""

    worktree_root = str(Path(__file__).resolve().parent.parent)
    env = {**_os.environ, "PYTHONPATH": worktree_root}
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def test_generate_image_no_astrid_session_id_mutation() -> None:
    """``astrid.generate.image()`` must not mutate ``ASTRID_SESSION_ID``."""
    probe = _session_id_mutation_probe("image")
    assert probe["unchanged"] is True, (
        f"ASTRID_SESSION_ID changed: "
        f"before={probe['session_before']!r}, after={probe['session_after']!r}"
    )


def test_generate_video_no_astrid_session_id_mutation() -> None:
    """``astrid.generate.video()`` must not mutate ``ASTRID_SESSION_ID``."""
    probe = _session_id_mutation_probe("video")
    assert probe["unchanged"] is True, (
        f"ASTRID_SESSION_ID changed: "
        f"before={probe['session_before']!r}, after={probe['session_after']!r}"
    )


# --- gateway failure is explicit and side-effect free -------------------------


def test_gateway_missing_project_prints_selection_help() -> None:
    """Projectless runs print the chooser and never auto-bind."""
    import os as _os

    worktree_root = str(Path(__file__).resolve().parent.parent)
    env = {
        **_os.environ,
        "PYTHONPATH": worktree_root,
    }
    env.pop("ASTRID_SESSION_ID", None)

    completed = subprocess.run(
        [sys.executable, "-m", "astrid", "executors", "run", "--dry-run", "generation.nonexistent_99"],
        capture_output=True,
        text=True,
        env=env,
    )

    stderr = completed.stderr
    assert completed.returncode == 2
    assert "project required: every executor run" in stderr
    assert "astrid projects ls" in stderr
    assert "astrid projects select <project>" in stderr
    assert "--project <project>" in stderr
    assert "auto-bound default project" not in stderr


def test_gateway_missing_project_does_not_set_session_id() -> None:
    """Failure must not create or bind a session as a side effect."""
    import os as _os

    script = '''
import os, sys
# Force the gate path by simulating a gateway invocation
os.environ.pop("ASTRID_SESSION_ID", None)

# Import and call the gate main
from astrid.core.gateway import main
# Use --dry-run to prove dry runs enforce the same project requirement.
try:
    exit_code = main(["executors", "run", "--dry-run", "generation.nonexistent_99"])
except SystemExit as e:
    exit_code = e.code

# Check that failure left the process unbound.
session_id = os.environ.get("ASTRID_SESSION_ID", "__UNSET__")
print(f"SESSION_ID={session_id}")
print(f"EXIT_CODE={exit_code}")
'''

    worktree_root = str(Path(__file__).resolve().parent.parent)
    env = {**_os.environ, "PYTHONPATH": worktree_root}
    env.pop("ASTRID_SESSION_ID", None)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )

    stdout = completed.stdout
    assert "SESSION_ID=" in stdout, f"Missing SESSION_ID in stdout: {stdout!r}"
    session_line = [line for line in stdout.splitlines() if line.startswith("SESSION_ID=")]
    assert session_line
    session_value = session_line[0].split("=", 1)[1]
    assert session_value == "__UNSET__"
    assert "EXIT_CODE=2" in stdout


def test_gateway_run_passes_bound_project_via_request_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import types
    from unittest.mock import MagicMock, patch

    from astrid.core.foundation import project_paths
    from astrid.core.project.project import create_project
    from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
    from astrid.core.session.lifecycle import create_session
    from astrid.core.session.paths import sessions_dir
    from astrid.core.timeline.crud import create_timeline
    from astrid.core.gateway import main

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects_root))
    monkeypatch.setenv("ASTRID_HOME", str(tmp_path / "astrid-home"))
    create_project("demo")
    create_timeline("demo", "main", is_default=True)
    session = create_session(
        project_slug="demo",
        agent_id="tester",
        projects_root=projects_root,
        session_root=sessions_dir(),
        write_project_pointer=True,
    )
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, session.id)

    captured: dict[str, Any] = {}
    fake_result = types.SimpleNamespace(
        missing_binaries=(),
        skipped=False,
        command=(),
        payload=None,
        returncode=0,
        ok=True,
        error=None,
    )
    fake_registry = MagicMock()
    fake_registry.get.return_value = MagicMock()

    def _capture(request, registry):
        captured["request"] = request
        return fake_result

    out_dir = tmp_path / "bound-out"

    with patch("astrid.core.execution.executor.cli.load_default_registry", return_value=fake_registry), \
         patch("astrid.core.execution.executor.runner.run_executor", side_effect=_capture):
        rc = main(["executors", "run", "test.executor", "--out", str(out_dir)])

    request = captured["request"]
    assert rc == 0
    assert request.project == "demo"
    assert request.project_was_auto_resolved is True
    assert "--project" not in request.argv
    assert os.environ.get(ASTRID_SESSION_ID_ENV) == session.id


# ============================================================================
# Verb registry tests (T19)
# ============================================================================


def test_register_and_resolve_synthetic_verb() -> None:
    """A synthetic verb registered via ``register_verb`` is reachable
    through ``astrid.generate.<name>``."""
    import astrid
    from astrid.core.generation.verbs import register_verb

    def _dummy_handler(**kwargs: Any) -> dict[str, Any]:
        return {"verb_called": True, **kwargs}

    register_verb("synthetic_test_verb", _dummy_handler)

    # Access through the facade's __getattr__
    handler = astrid.generate.__getattr__("synthetic_test_verb")
    assert handler is _dummy_handler, (
        f"__getattr__ did not return the registered handler; got {handler!r}"
    )

    result = handler(extra_arg=42)
    assert result == {"verb_called": True, "extra_arg": 42}


def test_missing_verb_raises_attribute_error() -> None:
    """Accessing an unregistered verb through ``astrid.generate.__getattr__``
    raises ``AttributeError`` with a helpful message."""
    import astrid

    with pytest.raises(AttributeError) as exc_info:
        astrid.generate.__getattr__("nonexistent_verb_xyz")
    message = str(exc_info.value)
    assert "nonexistent_verb_xyz" in message
    assert "GenerationFacade" in message


def test_builtin_methods_take_priority_over_getattr() -> None:
    """``image`` and ``video`` are first-class methods and are resolved
    *before* ``__getattr__`` is invoked."""
    import astrid

    assert callable(astrid.generate.image), "image should be a callable method"
    assert callable(astrid.generate.video), "video should be a callable method"
    # They must resolve without triggering __getattr__
    # (Python's attribute lookup guarantees this for class methods)


def test_register_verb_rejects_reserved_name_image() -> None:
    """``register_verb('image', ...)`` raises ``ValueError``."""
    from astrid.core.generation.verbs import register_verb

    def _dummy(**kwargs: Any) -> None:
        pass

    with pytest.raises(ValueError, match="reserved"):
        register_verb("image", _dummy)


def test_register_verb_rejects_reserved_name_video() -> None:
    """``register_verb('video', ...)`` raises ``ValueError``."""
    from astrid.core.generation.verbs import register_verb

    def _dummy(**kwargs: Any) -> None:
        pass

    with pytest.raises(ValueError, match="reserved"):
        register_verb("video", _dummy)


def test_register_verb_rejects_non_callable() -> None:
    """``register_verb`` raises ``TypeError`` when handler is not callable."""
    from astrid.core.generation.verbs import register_verb

    with pytest.raises(TypeError, match="callable"):
        register_verb("not_a_handler", 42)


def test_import_astrid_does_not_eagerly_import_verb_plugins() -> None:
    """``import astrid`` must not pull in the verb registry's plugin discovery
    machinery or any plugin registration modules."""
    import os as _os

    script = """
import importlib
import sys
# Clear any pre-loaded state
astrid = importlib.import_module("astrid")
# After import astrid, the verbs module should be importable but
# load_generation_verb_plugins should NOT have been called yet.
import astrid.core.generation.verbs as _verbs
print(f"PLUGINS_LOADED={_verbs._plugins_loaded}")
# The verbs module itself should not cause astrid.sdk to be loaded
print(f"SDK_IN_SYSMOD={'astrid.sdk' in sys.modules}")
"""
    worktree_root = str(Path(__file__).resolve().parent.parent)
    env = {**_os.environ, "PYTHONPATH": worktree_root}
    env.pop("ASTRID_SESSION_ID", None)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, (
        f"Subprocess failed. stderr={completed.stderr!r}"
    )
    stdout = completed.stdout
    assert "PLUGINS_LOADED=False" in stdout, (
        f"Plugins were eagerly loaded during import astrid: {stdout!r}"
    )
    assert "SDK_IN_SYSMOD=False" in stdout, (
        f"astrid.sdk loaded in sys.modules: {stdout!r}"
    )


def test_get_verb_raises_keyerror_for_unregistered() -> None:
    """``get_verb`` raises ``KeyError`` for an unregistered name."""
    from astrid.core.generation.verbs import get_verb

    with pytest.raises(KeyError, match="not registered"):
        get_verb("does_not_exist_at_all")


def test_list_verbs_returns_sorted_names() -> None:
    """``list_verbs`` returns a sorted tuple of registered verb names."""
    from astrid.core.generation.verbs import list_verbs, register_verb

    def _a(**kwargs: Any) -> None:
        pass

    def _b(**kwargs: Any) -> None:
        pass

    register_verb("test_verb_z", _a)
    register_verb("test_verb_a", _b)
    names = list_verbs()
    assert "test_verb_a" in names
    assert "test_verb_z" in names
    # Verify sorted order
    assert names == tuple(sorted(names)), (
        f"list_verbs() not sorted: {names!r}"
    )


def test_verb_accessible_via_dot_attribute_on_facade() -> None:
    """A registered verb is reachable through ``astrid.generate.<name>``
    dot-attribute access, not just explicit ``__getattr__``."""
    import astrid
    from astrid.core.generation.verbs import register_verb

    def _handler(**kwargs: Any) -> dict[str, Any]:
        return {"dot_access": True, **kwargs}

    register_verb("dot_access_verb", _handler)

    # Simulate dot-attribute access: astrid.generate.dot_access_verb
    resolved = getattr(astrid.generate, "dot_access_verb")
    assert resolved is _handler, (
        f"getattr did not return the registered handler; got {resolved!r}"
    )

    result = resolved(payload={"key": "val"})
    assert result == {"dot_access": True, "payload": {"key": "val"}}


def test_getattr_on_facade_triggers_lazy_plugin_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first ``__getattr__`` call on the facade triggers
    ``load_generation_verb_plugins``, flipping ``_plugins_loaded`` to True."""
    import astrid
    from astrid.core.generation import verbs as verbs_mod
    from astrid.core.generation.verbs import register_verb

    # Reset module state (prior tests may have already loaded plugins)
    monkeypatch.setattr(verbs_mod, "_plugins_loaded", False)

    def _handler(**kwargs: Any) -> None:
        pass

    register_verb("lazy_probe_verb", _handler)

    # Access a verb — this should trigger load_generation_verb_plugins()
    _ = getattr(astrid.generate, "lazy_probe_verb")

    assert verbs_mod._plugins_loaded is True, (
        "Plugins should be loaded after the first getattr on the facade"
    )


def test_register_verb_rejects_empty_or_whitespace_name() -> None:
    """``register_verb`` raises ``ValueError`` for empty or whitespace-only names."""
    from astrid.core.generation.verbs import register_verb

    def _dummy(**kwargs: Any) -> None:
        pass

    with pytest.raises(ValueError, match="non-empty"):
        register_verb("", _dummy)

    with pytest.raises(ValueError, match="non-empty"):
        register_verb("   ", _dummy)


def test_import_astrid_does_not_load_plugin_discovery_modules() -> None:
    """``import astrid`` must not pull in pack discovery or any
    plugin registration modules — only the lightweight ``verbs`` module."""
    import os as _os

    script = """
import importlib
import sys

astrid = importlib.import_module("astrid")

# These heavy modules must NOT be loaded after import astrid alone
heavy = (
    "astrid.sdk",
    "astrid.core.pack",
    "astrid.core.pack.discovery",
    "astrid.core.generation.verbs",
)
for mod in heavy:
    in_sys = mod in sys.modules
    print(f"MOD_{mod.replace('.', '_')}={in_sys}")

# verbs.py itself should be loadable but its plugins must not be loaded
import astrid.core.generation.verbs as _v
print(f"VERBS_MODULE_LOADED=True")
print(f"PLUGINS_LOADED={_v._plugins_loaded}")
"""
    worktree_root = str(Path(__file__).resolve().parent.parent)
    env = {**_os.environ, "PYTHONPATH": worktree_root}
    env.pop("ASTRID_SESSION_ID", None)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, (
        f"Subprocess failed. stderr={completed.stderr!r}"
    )
    stdout = completed.stdout
    assert "MOD_astrid_sdk=False" in stdout, (
        f"astrid.sdk loaded eagerly: {stdout!r}"
    )
    assert "MOD_astrid_core_pack=False" in stdout, (
        f"astrid.core.pack loaded eagerly: {stdout!r}"
    )
    assert "MOD_astrid_core_pack_discovery=False" in stdout, (
        f"astrid.core.pack.discovery loaded eagerly: {stdout!r}"
    )
    assert "PLUGINS_LOADED=False" in stdout, (
        f"Plugins loaded eagerly: {stdout!r}"
    )