"""Tests for ExecutorRegistry.fork() and OrchestratorRegistry.fork().

Covers shallow/deep fork, overwrite, priority-based shadowing.

All tests use tempfile.TemporaryDirectory for fixture packs.
No real LLM calls, no real network calls, no real git ops on actual repo.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from astrid.core.execution.executor.registry import (
    ExecutorRegistry,
    ExecutorRegistryError,
)
from astrid.core.execution.executor.schema import ExecutorDefinition
from astrid.core.execution.orchestrator.registry import (
    OrchestratorRegistry,
    OrchestratorRegistryError,
)
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.core.contracts.schema import CommandSpec, CachePolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_executor_def(id: str, **overrides) -> ExecutorDefinition:
    kwargs: dict = dict(
        id=id,
        name=id.split(".")[-1],
        kind="built_in",
        version="1.0.0",
        command=CommandSpec(argv=("echo", id)),
        cache=CachePolicy(mode="none"),
        metadata={},
    )
    kwargs.update(overrides)
    return ExecutorDefinition(**kwargs)


def _make_orchestrator_def(id: str, **overrides) -> OrchestratorDefinition:
    kwargs: dict = dict(
        id=id,
        name=id.split(".")[-1],
        kind="built_in",
        version="1.0.0",
        runtime=RuntimeSpec(kind="python", module="test.module", function="main"),
        metadata={},
    )
    kwargs.update(overrides)
    return OrchestratorDefinition(**kwargs)


def _write_executor_manifest(root: Path, executor_id: str, **extra_metadata) -> None:
    """Write a minimal executor.yaml (JSON format) to *root*."""
    content = {
        "id": executor_id,
        "name": executor_id.split(".")[-1],
        "kind": "built_in",
        "version": "1.0.0",
        "command": {"argv": ["echo", executor_id]},
        "cache": {"mode": "none"},
        "metadata": extra_metadata,
    }
    (root / "executor.yaml").write_text(
        json.dumps(content) + "\n", encoding="utf-8"
    )


def _write_orchestrator_manifest(root: Path, orchestrator_id: str, **extra_metadata) -> None:
    """Write a minimal orchestrator.yaml (JSON format) to *root*."""
    content = {
        "id": orchestrator_id,
        "name": orchestrator_id.split(".")[-1],
        "kind": "built_in",
        "version": "1.0.0",
        "runtime": {
            "kind": "command",
            "command": {"argv": ["echo", orchestrator_id]},
        },
        "metadata": extra_metadata,
    }
    (root / "orchestrator.yaml").write_text(
        json.dumps(content) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Executor fork tests
# ---------------------------------------------------------------------------


class TestExecutorFork:
    """Shallow and deep fork of executors."""

    def test_shallow_fork_creates_target_with_rewritten_manifest(self):
        """Fork an executor into a project dir; verify manifest id rewritten
        and .astrid_fork_state.json written."""
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            src_root = Path(src_tmp) / "src_executor"
            src_root.mkdir()
            _write_executor_manifest(src_root, "editorial.shots")

            registry = ExecutorRegistry()
            registry.register(
                _make_executor_def(
                    "editorial.shots",
                    metadata={"content_root": str(src_root), "source": "pack", "source_pack": "builtin"},
                )
            )

            target = registry.fork("editorial.shots", project_root=proj_tmp)

            assert target.exists()
            assert target.is_dir()
            # Manifest rewritten to local.<local_id>
            manifest = json.loads((target / "executor.yaml").read_text(encoding="utf-8"))
            assert manifest["id"] == "local.shots"
            assert manifest["metadata"]["forked_from"] == "editorial.shots"
            # Fork state file exists
            fork_state_path = target / ".astrid_fork_state.json"
            assert fork_state_path.is_file()
            fork_state = json.loads(fork_state_path.read_text(encoding="utf-8"))
            assert fork_state["forked_from"] == "editorial.shots"
            assert fork_state["upstream_version"] == "1.0.0"

    def test_shallow_fork_overwrite(self):
        """Fork first, then fork again with overwrite=True succeeds."""
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            src_root = Path(src_tmp) / "src_executor"
            src_root.mkdir()
            _write_executor_manifest(src_root, "editorial.shots")
            # Also write a marker file
            (src_root / "run.py").write_text("# original\n", encoding="utf-8")

            registry = ExecutorRegistry()
            registry.register(
                _make_executor_def(
                    "editorial.shots",
                    metadata={"content_root": str(src_root), "source": "pack", "source_pack": "builtin"},
                )
            )

            target1 = registry.fork("editorial.shots", project_root=proj_tmp)
            # Overwrite it with the same source (idempotent)
            target2 = registry.fork("editorial.shots", project_root=proj_tmp, overwrite=True)
            assert target1 == target2
            assert target1.exists()

    def test_shallow_fork_without_overwrite_raises(self):
        """Fork twice without overwrite raises ExecutorRegistryError."""
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            src_root = Path(src_tmp) / "src_executor"
            src_root.mkdir()
            _write_executor_manifest(src_root, "editorial.shots")

            registry = ExecutorRegistry()
            registry.register(
                _make_executor_def(
                    "editorial.shots",
                    metadata={"content_root": str(src_root), "source": "pack", "source_pack": "builtin"},
                )
            )

            registry.fork("editorial.shots", project_root=proj_tmp)
            with pytest.raises(ExecutorRegistryError, match="already exists"):
                registry.fork("editorial.shots", project_root=proj_tmp)

    def test_deep_fork_forks_dependencies(self):
        """Deep fork recursively forks depends_on executors."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create two executor source directories
            src_a = Path(tmp) / "exec_a"
            src_a.mkdir()
            _write_executor_manifest(src_a, "builtin.a")

            src_b = Path(tmp) / "exec_b"
            src_b.mkdir()
            _write_executor_manifest(src_b, "builtin.b")

            proj = Path(tmp) / "project"
            proj.mkdir()

            from astrid.core.execution.executor.schema import GraphMetadata

            registry = ExecutorRegistry()
            # Register 'b' first
            registry.register(
                _make_executor_def(
                    "builtin.b",
                    metadata={"content_root": str(src_b), "source": "pack", "source_pack": "builtin"},
                )
            )
            # Register 'a' with graph metadata (depends_on 'b') and higher
            # priority (lower number) so it wins over any shadowed entry.
            registry.register(
                _make_executor_def(
                    "builtin.a",
                    graph=GraphMetadata(depends_on=("builtin.b",)),
                    metadata={"priority": 10, "content_root": str(src_a), "source": "pack", "source_pack": "builtin"},
                )
            )

            target_a = registry.fork("builtin.a", project_root=proj, deep=True)

            assert target_a.exists()
            # Deep fork should also fork builtin.b
            target_b = Path(proj) / "astrid" / "packs" / "local" / "executors" / "b"
            assert target_b.exists()
            fork_state_b = json.loads((target_b / ".astrid_fork_state.json").read_text(encoding="utf-8"))
            assert fork_state_b["forked_from"] == "builtin.b"

    def test_fork_nonexistent_executor_raises(self):
        """Forking an unknown executor raises KeyError (unknown executor id)."""
        with tempfile.TemporaryDirectory() as proj_tmp:
            registry = ExecutorRegistry()
            with pytest.raises(KeyError, match="unknown executor id"):
                registry.fork("builtin.nonexistent", project_root=proj_tmp)


# ---------------------------------------------------------------------------
# Orchestrator fork tests
# ---------------------------------------------------------------------------


class TestOrchestratorFork:
    """Shallow and deep fork of orchestrators."""

    def test_shallow_fork_creates_target(self):
        """Fork an orchestrator into a project dir."""
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            src_root = Path(src_tmp) / "src_orch"
            src_root.mkdir()
            _write_orchestrator_manifest(src_root, "video_editing.hype")

            registry = OrchestratorRegistry()
            registry.register(
                _make_orchestrator_def(
                    "video_editing.hype",
                    metadata={"content_root": str(src_root), "source": "pack", "source_pack": "builtin"},
                )
            )

            target = registry.fork("video_editing.hype", project_root=proj_tmp)

            assert target.exists()
            manifest = json.loads((target / "orchestrator.yaml").read_text(encoding="utf-8"))
            assert manifest["id"] == "local.hype"
            fork_state = json.loads((target / ".astrid_fork_state.json").read_text(encoding="utf-8"))
            assert fork_state["forked_from"] == "video_editing.hype"

    def test_shallow_fork_overwrite(self):
        """Fork first, then overwrite."""
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            src_root = Path(src_tmp) / "src_orch"
            src_root.mkdir()
            _write_orchestrator_manifest(src_root, "video_editing.hype")

            registry = OrchestratorRegistry()
            registry.register(
                _make_orchestrator_def(
                    "video_editing.hype",
                    metadata={"content_root": str(src_root), "source": "pack", "source_pack": "builtin"},
                )
            )

            target1 = registry.fork("video_editing.hype", project_root=proj_tmp)
            target2 = registry.fork("video_editing.hype", project_root=proj_tmp, overwrite=True)
            assert target1 == target2
            assert target1.exists()

    def test_shallow_fork_without_overwrite_raises(self):
        """Fork twice without overwrite raises."""
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as proj_tmp:
            src_root = Path(src_tmp) / "src_orch"
            src_root.mkdir()
            _write_orchestrator_manifest(src_root, "video_editing.hype")

            registry = OrchestratorRegistry()
            registry.register(
                _make_orchestrator_def(
                    "video_editing.hype",
                    metadata={"content_root": str(src_root), "source": "pack", "source_pack": "builtin"},
                )
            )

            registry.fork("video_editing.hype", project_root=proj_tmp)
            with pytest.raises(OrchestratorRegistryError, match="already exists"):
                registry.fork("video_editing.hype", project_root=proj_tmp)

    def test_deep_fork_forks_child_executors(self):
        """Deep fork of orchestrator also forks child executors via ExecutorRegistry."""
        with tempfile.TemporaryDirectory() as tmp:
            src_orch = Path(tmp) / "src_orch"
            src_orch.mkdir()
            _write_orchestrator_manifest(src_orch, "builtin.pipeline")

            src_exec = Path(tmp) / "src_exec"
            src_exec.mkdir()
            _write_executor_manifest(src_exec, "rendering.render")

            proj = Path(tmp) / "project"
            proj.mkdir()

            exec_registry = ExecutorRegistry()
            exec_registry.register(
                _make_executor_def(
                    "rendering.render",
                    metadata={"content_root": str(src_exec), "source": "pack", "source_pack": "builtin"},
                )
            )

            orch_registry = OrchestratorRegistry(executor_registry=exec_registry)
            orch_registry.register(
                _make_orchestrator_def(
                    "builtin.pipeline",
                    child_executors=("rendering.render",),
                    metadata={"content_root": str(src_orch), "source": "pack", "source_pack": "builtin"},
                )
            )

            target_orch = orch_registry.fork("builtin.pipeline", project_root=proj, deep=True)
            assert target_orch.exists()

            # Child executor should also be forked
            target_exec = Path(proj) / "astrid" / "packs" / "local" / "executors" / "render"
            assert target_exec.exists()

    def test_fork_nonexistent_orchestrator_raises(self):
        """Forking an unknown orchestrator raises KeyError."""
        with tempfile.TemporaryDirectory() as proj_tmp:
            registry = OrchestratorRegistry()
            with pytest.raises(KeyError, match="unknown orchestrator id"):
                registry.fork("builtin.nonexistent", project_root=proj_tmp)


# ---------------------------------------------------------------------------
# Priority-based shadowing
# ---------------------------------------------------------------------------


class TestPriorityShadowing:
    """After fork, the local pack executor gets priority=10 and shadows
    the source executor (priority=30) when loaded together."""

    def test_local_fork_wins_over_source_by_priority(self):
        """Register source (priority=30) then local fork (priority=10);
        get() returns the local fork (lower priority number wins)."""
        registry = ExecutorRegistry()
        registry.register(
            _make_executor_def(
                "editorial.shots",
                version="1.0.0",
                metadata={"priority": 30, "source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_executor_def(
                "editorial.shots",
                version="2.0.0",
                metadata={"priority": 10, "source": "pack", "source_pack": "local"},
            )
        )

        winner = registry.get("editorial.shots")
        assert winner.version == "2.0.0"
        assert winner.metadata["source_pack"] == "local"

    def test_local_fork_wins_regardless_of_registration_order(self):
        """Local (priority=10) wins even when registered first."""
        registry = ExecutorRegistry()
        registry.register(
            _make_executor_def(
                "editorial.shots",
                version="2.0.0",
                metadata={"priority": 10, "source": "pack", "source_pack": "local"},
            )
        )
        registry.register(
            _make_executor_def(
                "editorial.shots",
                version="1.0.0",
                metadata={"priority": 30, "source": "pack", "source_pack": "builtin"},
            )
        )

        winner = registry.get("editorial.shots")
        assert winner.version == "2.0.0"
        assert winner.metadata["source_pack"] == "local"

    def test_orchestrator_priority_shadowing(self):
        """OrchestratorRegistry also supports priority shadowing."""
        registry = OrchestratorRegistry()
        registry.register(
            _make_orchestrator_def(
                "video_editing.hype",
                version="1.0.0",
                metadata={"priority": 30, "source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_orchestrator_def(
                "video_editing.hype",
                version="2.0.0",
                metadata={"priority": 10, "source": "pack", "source_pack": "local"},
            )
        )

        winner = registry.get("video_editing.hype")
        assert winner.version == "2.0.0"
        assert winner.metadata["source_pack"] == "local"
