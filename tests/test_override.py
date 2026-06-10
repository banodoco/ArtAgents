"""Tests for OverrideStore: set/remove/list overrides, persistence.

All tests use tempfile.TemporaryDirectory for the project root.
No real LLM calls, no real network calls, no real git ops on actual repo.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from astrid.core.pack.override import OverrideStore, OverrideStoreError


class TestOverrideStoreSetRemove:
    """Basic set and remove operations."""

    def test_set_and_resolve(self):
        """Set an override, then resolve it."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "editorial.shots", "local.shots")

            resolved = store.resolve("executor", "editorial.shots")
            assert resolved == "local.shots"

    def test_resolve_nonexistent_returns_none(self):
        """Resolving an id with no override returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            assert store.resolve("executor", "builtin.nonexistent") is None

    def test_remove_existing_override(self):
        """Remove an override, verify resolve returns None afterwards."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "editorial.shots", "local.shots")
            assert store.resolve("executor", "editorial.shots") == "local.shots"

            store.remove_override("executor", "editorial.shots")
            assert store.resolve("executor", "editorial.shots") is None

    def test_remove_nonexistent_noop(self):
        """Removing a non-existent override is a no-op."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            # Should not raise
            store.remove_override("executor", "builtin.nonexistent")

    def test_set_empty_type_raises(self):
        """Setting an override with empty type raises OverrideStoreError."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            with pytest.raises(OverrideStoreError, match="non-empty"):
                store.set_override("", "editorial.shots", "local.shots")

    def test_set_empty_id_raises(self):
        """Setting an override with empty id raises OverrideStoreError."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            with pytest.raises(OverrideStoreError, match="non-empty"):
                store.set_override("executor", "", "local.shots")

    def test_set_empty_target_raises(self):
        """Setting an override with empty target raises OverrideStoreError."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            with pytest.raises(OverrideStoreError, match="non-empty"):
                store.set_override("executor", "editorial.shots", "")


class TestOverrideStoreList:
    """list_overrides() returns correct grouped dict."""

    def test_empty_store_returns_empty_dict(self):
        """Empty store → empty dict."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            assert store.list_overrides() == {}

    def test_single_override_listed(self):
        """One override → single entry grouped by type."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "editorial.shots", "local.shots")
            result = store.list_overrides()
            assert result == {"executor": {"editorial.shots": "local.shots"}}

    def test_multiple_types_listed(self):
        """Overrides across different types are grouped."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "editorial.shots", "local.shots")
            store.set_override("orchestrator", "video_editing.hype", "local.hype")
            store.set_override("effects", "blur", "local.blur")

            result = store.list_overrides()
            assert "executor" in result
            assert "orchestrator" in result
            assert "effects" in result
            assert result["executor"]["editorial.shots"] == "local.shots"
            assert result["orchestrator"]["video_editing.hype"] == "local.hype"
            assert result["effects"]["blur"] == "local.blur"

    def test_multiple_overrides_same_type(self):
        """Multiple overrides of the same type are listed together."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "builtin.a", "local.a")
            store.set_override("executor", "builtin.b", "local.b")

            result = store.list_overrides()
            assert result == {"executor": {"builtin.a": "local.a", "builtin.b": "local.b"}}


class TestOverrideStorePersistence:
    """.overrides.json persistence."""

    def test_persist_creates_file(self):
        """Setting an override creates .overrides.json."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "editorial.shots", "local.shots")

            overrides_path = Path(tmp) / "astrid" / "packs" / "local" / ".overrides.json"
            assert overrides_path.is_file()

            data = json.loads(overrides_path.read_text(encoding="utf-8"))
            assert data == {"executor": {"editorial.shots": "local.shots"}}

    def test_persist_creates_parent_dirs(self):
        """Setting an override creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmp:
            # project_root has no astrid/packs/local yet
            assert not (Path(tmp) / "astrid").exists()

            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "editorial.shots", "local.shots")

            assert (Path(tmp) / "astrid" / "packs" / "local").is_dir()

    def test_load_from_existing_file(self):
        """OverrideStore loads existing .overrides.json on init."""
        with tempfile.TemporaryDirectory() as tmp:
            # Pre-create the .overrides.json
            overrides_dir = Path(tmp) / "astrid" / "packs" / "local"
            overrides_dir.mkdir(parents=True)
            (overrides_dir / ".overrides.json").write_text(
                json.dumps({"executor": {"editorial.shots": "local.shots"}}),
                encoding="utf-8",
            )

            store = OverrideStore(project_root=tmp)
            assert store.resolve("executor", "editorial.shots") == "local.shots"

    def test_remove_persists_deletion(self):
        """Removing an override is persisted to disk."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "builtin.a", "local.a")
            store.set_override("executor", "builtin.b", "local.b")
            store.remove_override("executor", "builtin.a")

            # Reload from disk
            store2 = OverrideStore(project_root=tmp)
            assert store2.resolve("executor", "builtin.a") is None
            assert store2.resolve("executor", "builtin.b") == "local.b"

    def test_overwrite_updates_file(self):
        """Setting the same key twice overwrites and persists."""
        with tempfile.TemporaryDirectory() as tmp:
            store = OverrideStore(project_root=tmp)
            store.set_override("executor", "editorial.shots", "local.shots_v1")
            store.set_override("executor", "editorial.shots", "local.shots_v2")

            # Reload
            store2 = OverrideStore(project_root=tmp)
            assert store2.resolve("executor", "editorial.shots") == "local.shots_v2"


class TestOverrideStoreRegistryIntegration:
    """OverrideStore wired into registries."""

    def test_executor_registry_get_respects_override(self):
        """ExecutorRegistry.get() returns overridden target definition."""
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.schema import ExecutorDefinition

        with tempfile.TemporaryDirectory() as tmp:
            override_store = OverrideStore(project_root=tmp)
            override_store.set_override("executor", "editorial.shots", "local.shots")

            registry = ExecutorRegistry(override_store=override_store)
            registry.register(
                ExecutorDefinition(
                    id="editorial.shots",
                    name="Shots",
                    kind="built_in",
                    version="1.0.0",
                    metadata={"source": "pack", "source_pack": "builtin"},
                )
            )
            registry.register(
                ExecutorDefinition(
                    id="local.shots",
                    name="Local Shots",
                    kind="built_in",
                    version="2.0.0",
                    metadata={"source": "pack", "source_pack": "local"},
                )
            )

            result = registry.get("editorial.shots")
            # The override routes editorial.shots → local.shots
            assert result.id == "local.shots"
            assert result.name == "Local Shots"
            assert "override_target" not in result.metadata

    def test_executor_registry_get_no_override_returns_winner(self):
        """Without override, get() returns the priority winner."""
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.schema import ExecutorDefinition

        with tempfile.TemporaryDirectory() as tmp:
            override_store = OverrideStore(project_root=tmp)

            registry = ExecutorRegistry(override_store=override_store)
            registry.register(
                ExecutorDefinition(
                    id="editorial.shots",
                    name="Shots",
                    kind="built_in",
                    version="1.0.0",
                    metadata={"source": "pack", "source_pack": "builtin", "priority": 30},
                )
            )

            result = registry.get("editorial.shots")
            assert result.id == "editorial.shots"
            assert result.name == "Shots"
