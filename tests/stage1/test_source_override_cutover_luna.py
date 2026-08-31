"""Regression tests for the literal source-pack cutover in §6.207."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from astrid.core.element.registry import ElementRegistry
from astrid.core.execution.executor.registry import ExecutorRegistry, load_pack_executors
from astrid.core.execution.generic_host import GenericPackHost
from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
from astrid.core.rendering.registry import RendererRegistry


@pytest.mark.parametrize("module_name", ["astrid.core.pack.override", "astrid.core.dirty"])
def test_retired_override_modules_are_not_reachable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


@pytest.mark.parametrize(
    "registry_type",
    [ExecutorRegistry, OrchestratorRegistry, ElementRegistry, RendererRegistry],
)
def test_registries_have_no_fork_or_override_authority(registry_type: type) -> None:
    signature = inspect.signature(registry_type)
    assert "override_store" not in signature.parameters
    assert "fork" not in registry_type.__dict__
    registry = registry_type()
    assert not hasattr(registry, "override_store")


def test_pack_discovery_assigns_no_local_shadow_priority() -> None:
    definitions = load_pack_executors(project_root=Path.cwd())
    assert definitions
    assert all(definition.metadata.get("priority") == 30 for definition in definitions)


def test_generic_host_discovers_canonical_pack_manifests() -> None:
    records = GenericPackHost(pack_roots=[Path("astrid/packs")]).discover()
    rendering = next(record for record in records if record.id == "rendering.render")
    assert rendering.source_root.parts[-5:] == (
        "astrid",
        "packs",
        "rendering",
        "executors",
        "render",
    )
    assert rendering.manifest_path is not None
    assert rendering.manifest_path.name == "executor.yaml"
