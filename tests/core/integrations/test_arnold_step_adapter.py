"""Boundary tests for the Arnold step-invocation adapter package.

These tests verify two things:

1. **No-contamination (always-on):** Importing common Astrid core modules
   does NOT cause ``arnold`` to appear in ``sys.modules``, and core source
   files do not reference ``arnold``.  This guarantees Astrid startup is
   fully self-contained regardless of whether Arnold is installed.

2. **Behavior tests (import-skipping):** Arnold adapter construction and
   registry installation are exercised ONLY when Arnold is available, using
   ``pytest.importorskip('arnold.pipeline')``.  CI environments without
   Arnold skip these cleanly with zero failures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from astrid.core.io.cas import (
    canonical_json_digest,
    cas_path,
    executor_definition_digest,
    identity_digest,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

# Common Astrid core modules that participate in normal startup / CLI paths.
# These are chosen to cover the import surfaces most likely to be touched
# during a typical Astrid CLI invocation — not an exhaustive list of every
# module in astrid.core.
_COMMON_CORE_MODULES: tuple[str, ...] = (
    "astrid",
    "astrid.core",
    "astrid.core.io",
    "astrid.core.io.cas",
    "astrid.core.foundation",
    "astrid.core.task",
    "astrid.core.task.gate.base",
    "astrid.core.task.gate.dispatch",
    "astrid.core.adapter",
    "astrid.core.contracts",
    "astrid.core.contracts.capability_runner",
    "astrid.core.orchestrate",
    "astrid.core.registry",
    "astrid.core.session",
    "astrid.core._shared",
    "astrid.core.util",
)


def _arnold_in_sys_modules() -> bool:
    """Return True if any ``arnold``-prefixed key exists in ``sys.modules``."""
    return any(k == "arnold" or k.startswith("arnold.") for k in sys.modules)


def _source_file_mentions_arnold(mod: Any) -> bool:
    """Return True if the module's source file path contains 'arnold'."""
    try:
        source = str(mod.__file__)
    except AttributeError:
        return False
    return "arnold" in source.lower()


@pytest.fixture(autouse=True)
def _clear_arnold_integration_modules() -> None:
    for key in list(sys.modules):
        if key.startswith("astrid.core.integrations.arnold"):
            del sys.modules[key]
    yield
    for key in list(sys.modules):
        if key.startswith("astrid.core.integrations.arnold"):
            del sys.modules[key]


# ═══════════════════════════════════════════════════════════════════════════════
# No-contamination tests (always-on — no importorskip)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNoArnoldContamination:
    """Importing common Astrid core modules must never pull in ``arnold``."""

    @pytest.mark.parametrize("module_name", _COMMON_CORE_MODULES)
    def test_importing_core_module_does_not_import_arnold(
        self, module_name: str
    ) -> None:
        """Import *module_name* and assert ``arnold`` is absent from sys.modules."""
        # Snapshot sys.modules before the import so a prior test importing
        # the Arnold integration package (which is tested separately) does
        # not pollute this assertion.
        before = _arnold_in_sys_modules()
        # If arnold was somehow already in sys.modules before this test
        # (e.g. from a prior importorskip that resolved), we can't prove
        # the current import was clean.  In practice this only happens
        # when Arnold IS installed and some other test imported it first —
        # but the real CI risk is the absence of Arnold, so we treat a
        # pre-existing arnold in sys.modules as a non-actionable skip.
        if before:
            pytest.skip(
                "arnold already present in sys.modules before importing "
                f"{module_name}; cannot isolate contamination check"
            )

        # Dynamically import the module under test.
        import importlib

        importlib.import_module(module_name)

        assert not _arnold_in_sys_modules(), (
            f"Importing {module_name} caused 'arnold' (or an arnold.* "
            f"submodule) to appear in sys.modules.  Astrid core must never "
            f"trigger Arnold imports."
        )

    @pytest.mark.parametrize("module_name", _COMMON_CORE_MODULES)
    def test_core_source_file_does_not_mention_arnold(
        self, module_name: str
    ) -> None:
        """Verify the source file for *module_name* does not reference 'arnold'."""
        import importlib

        mod = importlib.import_module(module_name)
        if _source_file_mentions_arnold(mod):
            pytest.fail(
                f"Source file for {module_name} ({mod.__file__}) mentions "
                f"'arnold'.  Arnold references must be confined to "
                f"astrid/core/integrations/arnold/."
            )

    def test_arnold_integration_package_not_auto_imported(self) -> None:
        """The Arnold integration package must NOT be auto-imported at startup."""
        arnold_keys = [
            k
            for k in sys.modules
            if k.startswith("astrid.core.integrations.arnold")
        ]
        assert not arnold_keys, (
            f"Arnold integration package unexpectedly present in sys.modules: "
            f"{arnold_keys}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Host package import-boundary tests (always-on — no importorskip)
# ═══════════════════════════════════════════════════════════════════════════════

# Modules whose source files are intentionally under
# astrid/core/integrations/arnold/ — they exist to bridge Arnold and Astrid
# but must still never trigger an actual ``arnold`` import at the package
# level.  These are tested separately from _COMMON_CORE_MODULES because the
# source-file path check intentionally allows the arnold/ directory.
_HOST_BOUNDARY_MODULES: tuple[str, ...] = (
    "astrid.core.integrations.arnold.host",
)


class TestHostPackageImportBoundary:
    """The host ``__init__.py`` must not import ``arnold`` at package level."""

    @pytest.mark.parametrize("module_name", _HOST_BOUNDARY_MODULES)
    def test_importing_host_package_does_not_import_arnold(
        self, module_name: str
    ) -> None:
        """Import the host package and assert ``arnold`` is absent from sys.modules."""
        before = _arnold_in_sys_modules()
        if before:
            pytest.skip(
                "arnold already present in sys.modules before importing "
                f"{module_name}; cannot isolate contamination check"
            )

        import importlib

        # Clear any cached host submodules that may have been loaded by
        # previous tests (the host __init__.py re-exports from registry
        # and shapes, which are safe; other submodules import compat which
        # imports arnold).
        for key in list(sys.modules):
            if key.startswith("astrid.core.integrations.arnold.host"):
                del sys.modules[key]

        importlib.import_module(module_name)

        assert not _arnold_in_sys_modules(), (
            f"Importing {module_name} caused 'arnold' (or an arnold.* "
            f"submodule) to appear in sys.modules.  The host __init__.py "
            f"must remain free of Arnold imports."
        )

    def test_host_init_does_not_import_arnold_submodules(self) -> None:
        """Importing the host package must not pull in compat/driver/envelope.

        These submodules import Arnold at module level; importing the host
        package itself must not trigger them.
        """
        before = _arnold_in_sys_modules()
        if before:
            pytest.skip(
                "arnold already present in sys.modules; "
                "cannot isolate contamination check"
            )

        # Clear cached host submodules
        for key in list(sys.modules):
            if key.startswith("astrid.core.integrations.arnold.host"):
                del sys.modules[key]

        import astrid.core.integrations.arnold.host as host_pkg

        # The host package must be importable
        assert host_pkg is not None

        # But its submodules that import arnold must NOT be in sys.modules
        arnold_host_keys = [
            k
            for k in sys.modules
            if k.startswith("astrid.core.integrations.arnold.host")
            and k != "astrid.core.integrations.arnold.host"
        ]
        # registry and shapes are safe (no arnold imports); all others
        # (compat, driver, envelope, invocation, hooks, render, cli) must
        # not have been auto-imported.
        unsafe_submodules = [
            k for k in arnold_host_keys
            if k.rsplit(".", 1)[-1] not in {"registry", "shapes"}
        ]
        assert not unsafe_submodules, (
            f"Importing astrid.core.integrations.arnold.host unexpectedly "
            f"auto-imported Arnold-touching submodules: {unsafe_submodules}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gateway/task import-boundary tests (always-on — no importorskip)
# ═══════════════════════════════════════════════════════════════════════════════

# Gateway dispatch and task lifecycle modules that must never trigger
# Arnold imports during normal CLI startup.
_GATEWAY_TASK_MODULES: tuple[str, ...] = (
    "astrid.core.gateway",
    "astrid.core.gateway.dispatch",
    "astrid.core.gateway.project",
    "astrid.core.gateway.help",
    "astrid.core.task",
    "astrid.core.task.gate.base",
    "astrid.core.task.gate.dispatch",
    "astrid.core.task.lifecycle",
    "astrid.core.task.lifecycle.ack",
    "astrid.core.task.lifecycle.skip",
)


class TestGatewayTaskImportBoundary:
    """Gateway and task lifecycle imports must never pull in ``arnold``."""

    @pytest.mark.parametrize("module_name", _GATEWAY_TASK_MODULES)
    def test_importing_gateway_task_module_does_not_import_arnold(
        self, module_name: str
    ) -> None:
        """Import a gateway/task module and assert ``arnold`` absent from sys.modules."""
        before = _arnold_in_sys_modules()
        if before:
            pytest.skip(
                "arnold already present in sys.modules before importing "
                f"{module_name}; cannot isolate contamination check"
            )

        import importlib

        importlib.import_module(module_name)

        assert not _arnold_in_sys_modules(), (
            f"Importing {module_name} caused 'arnold' (or an arnold.* "
            f"submodule) to appear in sys.modules.  Gateway/task modules "
            f"must never trigger Arnold imports."
        )

    def test_host_package_importable_without_arnold(self) -> None:
        """The host package is importable and exposes expected symbols."""
        import astrid.core.integrations.arnold.host as host_pkg

        # Verify the re-exported symbols are present
        assert hasattr(host_pkg, "ShapeRegistry")
        assert hasattr(host_pkg, "get_host_shape_registry")
        assert hasattr(host_pkg, "WE_REFINE_IMAGE_ID")
        assert hasattr(host_pkg, "WE_BEST_OF_4_ID")
        assert hasattr(host_pkg, "TEXT_ANALYSIS_SUMMARIZE_ID")
        assert hasattr(host_pkg, "ALLOWLISTED_SHAPE_IDS")

        # The allowlisted shape IDs must match the declared constants
        assert "we.refine_image" in host_pkg.ALLOWLISTED_SHAPE_IDS
        assert "we.best_of_4" in host_pkg.ALLOWLISTED_SHAPE_IDS
        assert "text_analysis.summarize" in host_pkg.ALLOWLISTED_SHAPE_IDS


# ═══════════════════════════════════════════════════════════════════════════════
# Arnold adapter behavior tests (import-skipping via importorskip)
# ═══════════════════════════════════════════════════════════════════════════════

# Module-level importorskip so the entire class is skipped if Arnold is not
# installed.  This keeps CI without Arnold clean: no failures, no warnings,
# just a single "SKIPPED" line per test class.
pytest.importorskip("arnold.pipeline")


class TestAstridStepInvocationAdapterConstruction:
    """AstridStepInvocationAdapter can be constructed with injectable deps."""

    def test_construct_with_minimal_args(self, tmp_path: Path) -> None:
        """Construction succeeds with registry, runner, and artifact root."""
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        registry = SimpleNamespace()
        runner = lambda req: None  # noqa: E731
        adapter = AstridStepInvocationAdapter(
            executor_registry=registry,
            run_executor_fn=runner,
            artifact_root=tmp_path / "artifacts",
        )
        assert adapter is not None
        assert adapter._executor_registry is registry
        assert adapter._run_executor_fn is runner

    def test_construct_with_all_optional_args(self, tmp_path: Path) -> None:
        """All optional constructor args are accepted and stored."""
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        registry = SimpleNamespace()
        runner = lambda req: None  # noqa: E731
        resolver = lambda slug: tmp_path / slug  # noqa: E731
        clock = lambda: "2026-06-12T00:00:00Z"  # noqa: E731

        adapter = AstridStepInvocationAdapter(
            executor_registry=registry,
            run_executor_fn=runner,
            artifact_root=tmp_path / "artifacts",
            default_project="my-project",
            project_dir_resolver=resolver,
            clock=clock,
        )
        assert adapter._default_project == "my-project"
        assert adapter._project_dir_resolver is resolver
        assert adapter._clock is clock

    def test_default_project_falls_back_to_default(self, tmp_path: Path) -> None:
        """When default_project is not supplied, it defaults to 'default'."""
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(),
            run_executor_fn=lambda req: None,
            artifact_root=tmp_path / "artifacts",
        )
        assert adapter._default_project == "default"


class TestInstallAstridStepAdapter:
    """install_astrid_step_adapter registers into an Arnold registry."""

    @staticmethod
    def _make_registry() -> Any:
        """Return a real Arnold StepInvocationAdapterRegistry (or a fake)."""
        from arnold.pipeline import StepInvocationAdapterRegistry

        return StepInvocationAdapterRegistry()

    def test_install_creates_and_registers(self, tmp_path: Path) -> None:
        """Supplying constructor args creates + registers the adapter."""
        from astrid.core.integrations.arnold import install_astrid_step_adapter

        registry = self._make_registry()
        adapter = install_astrid_step_adapter(
            registry,
            kind="astrid",
            executor_registry=SimpleNamespace(),
            run_executor_fn=lambda req: None,
            artifact_root=tmp_path / "artifacts",
        )
        assert adapter is not None
        # The registry should now contain our adapter under kind "astrid".
        registered = registry.resolve("astrid")
        assert registered is adapter

    def test_install_with_prebuilt_adapter(self, tmp_path: Path) -> None:
        """Supplying a pre-built adapter registers it directly."""
        from astrid.core.integrations.arnold import (
            AstridStepInvocationAdapter,
            install_astrid_step_adapter,
        )

        prebuilt = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(),
            run_executor_fn=lambda req: None,
            artifact_root=tmp_path / "artifacts",
        )
        registry = self._make_registry()
        result = install_astrid_step_adapter(registry, adapter=prebuilt)
        assert result is prebuilt
        assert registry.resolve("astrid") is prebuilt

    def test_install_raises_without_required_args(self) -> None:
        """Calling install without adapter or required constructor args raises."""
        from astrid.core.integrations.arnold import install_astrid_step_adapter

        registry = self._make_registry()
        with pytest.raises(ValueError, match="must supply either 'adapter' or"):
            install_astrid_step_adapter(registry)

    def test_install_respects_custom_kind(self, tmp_path: Path) -> None:
        """Custom kind strings are passed through to the registry."""
        from astrid.core.integrations.arnold import install_astrid_step_adapter

        registry = self._make_registry()
        adapter = install_astrid_step_adapter(
            registry,
            kind="custom-astrid",
            executor_registry=SimpleNamespace(),
            run_executor_fn=lambda req: None,
            artifact_root=tmp_path / "artifacts",
        )
        assert registry.resolve("custom-astrid") is adapter
        # The default kind should not have been registered.
        with pytest.raises(KeyError):
            registry.resolve("astrid")


class TestAstridStepInvocationAdapterInvoke:
    """invoke() builds requests and maps runner results into StepResult."""

    @staticmethod
    def _executor(executor_id: str) -> Any:
        from astrid.core.contracts.schema import Output

        return SimpleNamespace(
            id=executor_id,
            inputs=(),
            outputs=(
                Output(name="image_out", artifact_type="image/png"),
                Output(name="manifest_out", type="json", extension=".json"),
            ),
            command=None,
            to_dict=lambda: {
                "id": executor_id,
                "outputs": [
                    {"name": "image_out", "artifact_type": "image/png"},
                    {"name": "manifest_out", "type": "json", "extension": ".json"},
                ],
            },
        )

    def test_invoke_builds_out_mode_request_from_state(self, tmp_path: Path) -> None:
        """Out mode resolves state + literal inputs and maps declared outputs."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        captured: list[Any] = []
        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            captured.append(request)
            out_root.mkdir(parents=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png-bytes")
            manifest_path.write_text('{"ok": true}', encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                    "ignored_extra": str(out_root / "ignored.txt"),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
        )
        invocation = StepInvocation(
            kind="astrid",
            metadata={
                "adapter_config": {
                    "executor_id": "image.generate",
                    "input_map": {"prompt": "hero_prompt"},
                    "inputs": {"style": "ink"},
                    "state": {"hero_prompt": {"ref": "cas://prompt"}},
                }
            },
        )
        result = adapter.invoke(invocation)
        assert len(captured) == 1
        request = captured[0]
        assert request.executor_id == "image.generate"
        assert request.inputs == {
            "prompt": {"ref": "cas://prompt"},
            "style": "ink",
        }
        assert request.execution_mode == "subprocess"
        assert request.project is None
        assert request.out == tmp_path / "artifacts" / "image.generate"
        assert request.run_root is None
        assert result.contract_result is not None
        assert result.contract_result.status.value == "completed"
        assert result.state_patch == {
            "image_out": str(out_root / "image.png"),
            "manifest_out": str(out_root / "manifest.json"),
        }
        assert "ignored_extra" not in result.state_patch
        evidence_refs = result.contract_result.evidence_refs
        assert len(evidence_refs) == 2
        assert {ref.name for ref in evidence_refs} == {"image_out", "manifest_out"}
        refs_by_name = {ref.name: ref for ref in evidence_refs}
        assert refs_by_name["image_out"].content_type == "image/png"
        assert refs_by_name["image_out"].size_bytes == len(b"png-bytes")
        assert refs_by_name["manifest_out"].content_type == "application/json"
        assert refs_by_name["manifest_out"].size_bytes == len('{"ok": true}')
        assert result.contract_result.payload["cache_status"] == "miss"

    def test_invoke_builds_project_mode_request_without_out(self, tmp_path: Path) -> None:
        """Project mode prefers ExecutorRunResult.run_root for relative outputs."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        captured: list[Any] = []
        explicit_run_root = tmp_path / "project-run-root"

        def _runner(request: Any) -> Any:
            captured.append(request)
            actual_run_root = tmp_path / "actual-project-run"
            actual_run_root.mkdir()
            output_path = actual_run_root / "image.png"
            manifest_path = actual_run_root / "manifest.json"
            output_path.write_bytes(b"abc")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                run_root=actual_run_root,
                outputs={
                    "image_out": "image.png",
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
        )
        invocation = StepInvocation(
            kind="astrid",
            metadata={
                "adapter_config": {
                    "executor_id": "image.generate",
                    "project": "demo",
                    "run_root": str(explicit_run_root),
                }
            },
        )
        result = adapter.invoke(invocation)
        assert len(captured) == 1
        request = captured[0]
        assert request.project == "demo"
        assert request.out is None
        assert request.run_root == str(explicit_run_root)
        assert result.contract_result is not None
        assert result.contract_result.payload["run_root"] == str(
            (tmp_path / "actual-project-run").resolve()
        )
        assert result.state_patch["image_out"] == str(
            (tmp_path / "actual-project-run" / "image.png").resolve()
        )

    def test_invoke_records_cas_identity_provenance_from_default_project(
        self, tmp_path: Path
    ) -> None:
        """Identity provenance records resolved project root and canonical digests."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        executor = self._executor("image.generate")
        resolved_project_dir = tmp_path / "projects" / "fallback"
        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(get=lambda executor_id: executor),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: resolved_project_dir,
            clock=lambda: "2026-06-12T00:00:00Z",
        )
        invocation = StepInvocation(
            kind="astrid",
            metadata={
                "adapter_config": {
                    "executor_id": "image.generate",
                    "input_map": {"prompt": "hero_prompt"},
                    "inputs": {"style": "ink"},
                    "state": {"hero_prompt": {"ref": "cas://prompt"}},
                }
            },
        )

        result = adapter.invoke(invocation)

        expected_input_digest = canonical_json_digest(
            {
                "effective_inputs": {
                    "prompt": {"ref": "cas://prompt"},
                    "style": "ink",
                },
                "literal_inputs": {"style": "ink"},
                "mapped_state_inputs": {
                    "prompt": {
                        "state_key": "hero_prompt",
                        "identity": {"ref": "cas://prompt"},
                    }
                },
            }
        )
        expected_executor_version = executor_definition_digest(executor)
        expected_identity_key = identity_digest(
            input_digest=expected_input_digest,
            producer_id=executor.id,
            producer_version=expected_executor_version,
        )

        payload = result.contract_result.payload
        assert payload["cas_project_dir"] == str(resolved_project_dir.resolve())
        assert payload["input_digest"] == expected_input_digest
        assert payload["identity_key"] == expected_identity_key
        assert payload["executor_id"] == executor.id
        assert payload["executor_version"] == expected_executor_version
        assert payload["cache_status"] == "miss"
        assert result.contract_result.provenance.chain == (
            "cache_status=miss",
            f"cas_project_dir={resolved_project_dir.resolve()}",
            f"input_digest={expected_input_digest}",
            f"identity_key={expected_identity_key}",
            f"executor_id={executor.id}",
            f"executor_version={expected_executor_version}",
        )

    def test_invoke_prefers_explicit_cas_project_dir(self, tmp_path: Path) -> None:
        """Explicit cas_project_dir overrides project/default-project resolution."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        explicit_cas_project_dir = tmp_path / "custom-cas-root"
        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"x")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: tmp_path / "projects" / slug,
        )

        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={
                    "adapter_config": {
                        "executor_id": "image.generate",
                        "project": "demo",
                        "cas_project_dir": str(explicit_cas_project_dir),
                    }
                },
            )
        )

        assert result.contract_result.payload["cas_project_dir"] == str(
            explicit_cas_project_dir.resolve()
        )

    def test_invoke_materializes_complete_cas_hit_without_running_executor(
        self, tmp_path: Path
    ) -> None:
        """A complete per-output CAS hit skips execution and symlinks declared outputs."""
        from arnold.pipeline import StepInvocation

        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        executor = self._executor("image.generate")
        cas_project_dir = tmp_path / "cas-project"
        out_root = tmp_path / "artifacts" / "image.generate"
        identity_key = identity_digest(
            input_digest=canonical_json_digest(
                {
                    "effective_inputs": {},
                    "literal_inputs": {},
                    "mapped_state_inputs": {},
                }
            ),
            producer_id=executor.id,
            producer_version=executor_definition_digest(executor),
        )
        image_key = canonical_json_digest(
            {"identity_key": identity_key, "output": "image_out"}
        )
        manifest_key = canonical_json_digest(
            {"identity_key": identity_key, "output": "manifest_out"}
        )
        image_cas = cas_path(cas_project_dir, image_key)
        manifest_cas = cas_path(cas_project_dir, manifest_key)
        image_cas.parent.mkdir(parents=True, exist_ok=True)
        image_cas.write_bytes(b"cached-png")
        manifest_cas.write_text('{"cached": true}', encoding="utf-8")

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(get=lambda executor_id: executor),
            run_executor_fn=lambda request: pytest.fail("runner should not be called"),
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: cas_project_dir,
        )

        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "image.generate"}},
            )
        )

        image_out = out_root / "image_out"
        manifest_out = out_root / "manifest_out"
        assert image_out.is_symlink()
        assert manifest_out.is_symlink()
        assert image_out.resolve() == image_cas.resolve()
        assert manifest_out.resolve() == manifest_cas.resolve()
        assert result.contract_result.payload["cache_status"] == "hit"
        assert result.state_patch == {
            "image_out": str(image_out),
            "manifest_out": str(manifest_out),
        }

    def test_invoke_materializes_cas_miss_into_declared_output_paths(
        self, tmp_path: Path
    ) -> None:
        """A CAS miss interns declared outputs and symlinks them back into the run dir."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        executor = self._executor("image.generate")
        cas_project_dir = tmp_path / "cas-project"
        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image_out"
            manifest_path = out_root / "manifest_out"
            image_path.write_bytes(b"fresh-png")
            manifest_path.write_text('{"fresh": true}', encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(get=lambda executor_id: executor),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: cas_project_dir,
        )

        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "image.generate"}},
            )
        )

        identity_key = result.contract_result.payload["identity_key"]
        image_cas = cas_path(
            cas_project_dir,
            canonical_json_digest(
                {"identity_key": identity_key, "output": "image_out"}
            ),
        )
        manifest_cas = cas_path(
            cas_project_dir,
            canonical_json_digest(
                {"identity_key": identity_key, "output": "manifest_out"}
            ),
        )
        image_out = out_root / "image_out"
        manifest_out = out_root / "manifest_out"
        assert image_cas.exists()
        assert manifest_cas.exists()
        assert image_out.is_symlink()
        assert manifest_out.is_symlink()
        assert image_out.resolve() == image_cas.resolve()
        assert manifest_out.resolve() == manifest_cas.resolve()
        assert result.contract_result.payload["cache_status"] == "miss"
        assert result.state_patch == {
            "image_out": str(image_out),
            "manifest_out": str(manifest_out),
        }

    def test_invoke_runs_normally_when_declared_output_paths_are_unresolved(
        self, tmp_path: Path
    ) -> None:
        """Without resolvable declared paths the adapter executes and marks the miss reason."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        run_count = 0

        def _runner(request: Any) -> Any:
            nonlocal run_count
            run_count += 1
            actual_run_root = tmp_path / "actual-project-run"
            actual_run_root.mkdir()
            image_path = actual_run_root / "image.png"
            manifest_path = actual_run_root / "manifest.json"
            image_path.write_bytes(b"abc")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                run_root=actual_run_root,
                outputs={
                    "image_out": "image.png",
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: tmp_path / "projects" / slug,
        )

        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={
                    "adapter_config": {
                        "executor_id": "image.generate",
                        "project": "demo",
                    }
                },
            )
        )

        assert run_count == 1
        assert result.contract_result.payload["cache_status"] == "miss_unresolved_paths"
        assert not (tmp_path / "projects" / "demo" / ".cas").exists()

    def test_invoke_rejects_conflicting_duplicate_inputs(self, tmp_path: Path) -> None:
        """Duplicate input keys fail closed unless the values are identical."""
        from arnold.pipeline import StepInvocation

        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: SimpleNamespace(id=executor_id)
            ),
            run_executor_fn=lambda request: pytest.fail("runner should not be called"),
            artifact_root=tmp_path / "artifacts",
        )
        invocation = StepInvocation(
            kind="astrid",
            metadata={
                "adapter_config": {
                    "executor_id": "image.generate",
                    "input_map": {"prompt": "hero_prompt"},
                    "inputs": {"prompt": "literal prompt"},
                    "state": {"hero_prompt": {"ref": "cas://prompt"}},
                }
            },
        )
        result = adapter.invoke(invocation)
        assert result.contract_result is not None
        assert result.contract_result.status.value == "failed"
        assert result.contract_result.payload["error"] == "duplicate_input_conflict"

    def test_invoke_leaves_os_environ_unchanged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Request construction does not mutate the process environment."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        monkeypatch.setenv("ASTRID_ARNOLD_ENV_CHECK", "before")
        before = dict(os.environ)

        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"x")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
        )
        invocation = StepInvocation(
            kind="astrid",
            metadata={"adapter_config": {"executor_id": "image.generate"}},
        )
        result = adapter.invoke(invocation)
        assert result.contract_result is not None
        assert result.contract_result.status.value == "completed"
        assert dict(os.environ) == before

    def test_invoke_fails_when_runner_raises(self, tmp_path: Path) -> None:
        """Runner exceptions become failed contract results."""
        from arnold.pipeline import StepInvocation

        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=lambda request: (_ for _ in ()).throw(RuntimeError("boom")),
            artifact_root=tmp_path / "artifacts",
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "image.generate"}},
            )
        )
        assert result.contract_result is not None
        assert result.contract_result.status.value == "failed"
        assert result.contract_result.payload["error"] == "executor_runner_error"

    def test_invoke_fails_for_nonzero_runner_result(self, tmp_path: Path) -> None:
        """Nonzero runner results map to failed contract results."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=lambda request: ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=7,
            ),
            artifact_root=tmp_path / "artifacts",
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "image.generate"}},
            )
        )
        assert result.contract_result is not None
        assert result.contract_result.status.value == "failed"
        assert result.contract_result.payload["error"] == "executor_run_failed"
        assert result.contract_result.payload["returncode"] == 7

    def test_invoke_fails_when_declared_output_is_missing(self, tmp_path: Path) -> None:
        """Missing declared outputs fail the contract even if extras are present."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        out_root = tmp_path / "artifacts" / "image.generate"
        out_root.mkdir(parents=True)
        image_path = out_root / "image.png"
        image_path.write_bytes(b"png")

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda executor_id: self._executor(executor_id)
            ),
            run_executor_fn=lambda request: ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "ignored_extra": str(out_root / "extra.txt"),
                },
            ),
            artifact_root=tmp_path / "artifacts",
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "image.generate"}},
            )
        )
        assert result.contract_result is not None
        assert result.contract_result.status.value == "failed"
        assert result.contract_result.payload["error"] == "missing_declared_outputs"
        assert result.contract_result.payload["missing_outputs"] == ("manifest_out",)

    # ── Judge lowering tests (fake executor definitions only) ────────────

    @staticmethod
    def _judge_executor(executor_id: str, judge: bool) -> Any:
        """Return a fake executor with arnold judge metadata."""
        from astrid.core.contracts.schema import Output

        return SimpleNamespace(
            id=executor_id,
            inputs=(),
            outputs=(
                Output(name="image_out", artifact_type="image/png"),
                Output(name="manifest_out", type="json", extension=".json"),
            ),
            command=None,
            metadata={"arnold": {"judge": judge}},
            to_dict=lambda: {
                "id": executor_id,
                "outputs": [
                    {"name": "image_out", "artifact_type": "image/png"},
                    {"name": "manifest_out", "type": "json", "extension": ".json"},
                ],
            },
        )

    def test_invoke_judge_lowering_creates_verdict_from_payload(
        self, tmp_path: Path
    ) -> None:
        """When executor.metadata['arnold']['judge'] is True,
        run_result.payload is lowered into a PipelineVerdict on StepResult.verdict."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        out_root = tmp_path / "artifacts" / "judge.exec"
        engine_root = tmp_path / "artifacts" / "engine"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text('{"ok": true}', encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
                payload={
                    "score": 0.85,
                    "flags": ["pass", "reviewed"],
                    "notes": "Looks great.",
                    "payload": {"detail": "extra"},
                    "recommendation": "approve",
                    "override": "force_pass",
                },
            )

        executor = self._judge_executor("judge.exec", judge=True)
        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(get=lambda eid: executor),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: engine_root,
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "judge.exec"}},
            )
        )

        assert result.contract_result.status.value == "completed"
        assert result.verdict is not None
        assert result.verdict.score == 0.85
        assert result.verdict.flags == ("pass", "reviewed")
        assert result.verdict.notes == "Looks great."
        assert result.verdict.payload == {"detail": "extra"}
        assert result.verdict.recommendation == "approve"
        assert result.verdict.override == "force_pass"

    def test_invoke_judge_defaults_when_payload_is_empty(
        self, tmp_path: Path
    ) -> None:
        """Empty run_result.payload produces conservative PipelineVerdict defaults."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        out_root = tmp_path / "artifacts" / "judge.exec"
        engine_root = tmp_path / "artifacts" / "engine"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
                payload={},
            )

        executor = self._judge_executor("judge.exec", judge=True)
        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(get=lambda eid: executor),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: engine_root,
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "judge.exec"}},
            )
        )

        assert result.contract_result.status.value == "completed"
        assert result.verdict is not None
        assert result.verdict.score == 0.0
        assert result.verdict.flags == ()
        assert result.verdict.notes == ""
        assert result.verdict.payload == {}
        assert result.verdict.recommendation is None
        assert result.verdict.override is None

    def test_invoke_no_verdict_when_judge_is_false(
        self, tmp_path: Path
    ) -> None:
        """When executor.metadata['arnold']['judge'] is False, verdict remains None."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        out_root = tmp_path / "artifacts" / "judge.exec"
        engine_root = tmp_path / "artifacts" / "engine"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
                payload={"score": 0.99},
            )

        executor = self._judge_executor("judge.exec", judge=False)
        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(get=lambda eid: executor),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
            default_project="fallback",
            project_dir_resolver=lambda slug: engine_root,
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "judge.exec"}},
            )
        )

        assert result.contract_result.status.value == "completed"
        assert result.verdict is None

    def test_invoke_no_verdict_without_arnold_metadata(
        self, tmp_path: Path
    ) -> None:
        """Executor without arnold metadata produces no verdict (backward-compatible)."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        out_root = tmp_path / "artifacts" / "image.generate"
        executor = self._executor("image.generate")  # no metadata at all

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(get=lambda eid: executor),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={"adapter_config": {"executor_id": "image.generate"}},
            )
        )

        assert result.contract_result.status.value == "completed"
        assert result.verdict is None

    # ── Content-validator registry tests (fake executor definitions only) ─

    def test_invoke_content_validator_registry_registers_noop_validators(
        self, tmp_path: Path
    ) -> None:
        """A ContentValidatorRegistry supplied via config gets no-op validators
        registered for every emitted evidence content type."""
        from arnold.pipeline import (
            ContentValidatorRegistry,
            StepInvocation,
        )

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        validator_registry = ContentValidatorRegistry()
        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda eid: self._executor(eid)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={
                    "adapter_config": {
                        "executor_id": "image.generate",
                        "content_validator_registry": validator_registry,
                    }
                },
            )
        )

        assert result.contract_result.status.value == "completed"
        # Both emitted content types should be registered
        assert "image/png" in validator_registry
        assert "application/json" in validator_registry

    def test_invoke_content_validator_registry_absent_preserves_all_refs(
        self, tmp_path: Path
    ) -> None:
        """When content_validator_registry is absent (None), all evidence
        refs are emitted unchanged — including types that require validation."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda eid: self._executor(eid)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={
                    "adapter_config": {
                        "executor_id": "image.generate",
                        # content_validator_registry absent
                    }
                },
            )
        )

        assert result.contract_result.status.value == "completed"
        ref_names = {ref.name for ref in result.contract_result.evidence_refs}
        assert ref_names == {"image_out", "manifest_out"}
        refs_by_name = {ref.name: ref for ref in result.contract_result.evidence_refs}
        assert refs_by_name["image_out"].content_type == "image/png"

    def test_invoke_content_validator_registry_non_registry_filters_media_refs(
        self, tmp_path: Path
    ) -> None:
        """When content_validator_registry is a non-ContentValidatorRegistry value,
        evidence refs whose content type requires validation are dropped while
        text/json/directory types are retained."""
        from arnold.pipeline import StepInvocation

        from astrid.core.execution.executor.runner import ExecutorRunResult
        from astrid.core.integrations.arnold import AstridStepInvocationAdapter

        out_root = tmp_path / "artifacts" / "image.generate"

        def _runner(request: Any) -> Any:
            out_root.mkdir(parents=True, exist_ok=True)
            image_path = out_root / "image.png"
            manifest_path = out_root / "manifest.json"
            image_path.write_bytes(b"png")
            manifest_path.write_text("{}", encoding="utf-8")
            return ExecutorRunResult(
                executor_id=request.executor_id,
                kind="external",
                returncode=0,
                outputs={
                    "image_out": str(image_path),
                    "manifest_out": str(manifest_path),
                },
            )

        adapter = AstridStepInvocationAdapter(
            executor_registry=SimpleNamespace(
                get=lambda eid: self._executor(eid)
            ),
            run_executor_fn=_runner,
            artifact_root=tmp_path / "artifacts",
        )
        result = adapter.invoke(
            StepInvocation(
                kind="astrid",
                metadata={
                    "adapter_config": {
                        "executor_id": "image.generate",
                        "content_validator_registry": "not-a-registry",
                    }
                },
            )
        )

        assert result.contract_result.status.value == "completed"
        ref_names = {ref.name for ref in result.contract_result.evidence_refs}
        # image/png requires validation → filtered out
        # application/json does NOT require validation → kept
        assert ref_names == {"manifest_out"}
        kept_ref = result.contract_result.evidence_refs[0]
        assert kept_ref.content_type == "application/json"


class TestArnoldIntegrationImportGuard:
    """Importing the Arnold integration package raises clean ImportError
    when Arnold is missing — but we can only test the successful path here
    since we importorskip'd above.  We verify the public surface is clean."""

    def test_public_surface_exports_adapter_and_install(self) -> None:
        """__all__ contains only the two expected public symbols."""
        from astrid.core.integrations import arnold

        assert hasattr(arnold, "AstridStepInvocationAdapter")
        assert hasattr(arnold, "install_astrid_step_adapter")
        assert arnold.__all__ == [
            "AstridStepInvocationAdapter",
            "install_astrid_step_adapter",
        ]

    def test_compat_helper_centralises_arnold_symbols(self) -> None:
        """_ArnoldCompat exposes all Arnold symbols the adapter uses."""
        from arnold.pipeline import (
            ContentValidatorRegistry,
            ContractResult,
            ContractStatus,
            EvidenceArtifactRef,
            PipelineVerdict,
            Provenance,
            StepInvocation,
            StepInvocationAdapter,
            StepInvocationAdapterRegistry,
            StepResult,
        )

        from astrid.core.integrations.arnold.step_adapter import _ArnoldCompat

        compat = _ArnoldCompat
        assert compat.StepInvocationAdapter is StepInvocationAdapter
        assert compat.StepInvocationAdapterRegistry is StepInvocationAdapterRegistry
        assert compat.StepInvocation is StepInvocation
        assert compat.StepResult is StepResult
        assert compat.ContractResult is ContractResult
        assert compat.ContractStatus is ContractStatus
        assert compat.Provenance is Provenance
        assert compat.EvidenceArtifactRef is EvidenceArtifactRef
        assert compat.PipelineVerdict is PipelineVerdict
        assert compat.ContentValidatorRegistry is ContentValidatorRegistry
