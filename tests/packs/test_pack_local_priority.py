"""Tests for local-pack priority (10) vs non-local (30) shadowing.

Verifies both registration orders and that priority-based shadowing
works correctly for executors and orchestrators.

All tests use inline definitions — no real registry loads.
No real LLM calls, no real network calls, no real git ops on actual repo.
"""

from __future__ import annotations

from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.schema import ExecutorDefinition
from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec


def _make_exec_def(id: str, *, priority: int, pack_id: str) -> ExecutorDefinition:
    return ExecutorDefinition(
        id=id,
        name=id.split(".")[-1],
        kind="built_in",
        version="1.0.0",
        metadata={"priority": priority, "source": "pack", "source_pack": pack_id},
    )


def _make_orch_def(id: str, *, priority: int, pack_id: str) -> OrchestratorDefinition:
    return OrchestratorDefinition(
        id=id,
        name=id.split(".")[-1],
        kind="built_in",
        version="1.0.0",
        runtime=RuntimeSpec(kind="python", module="test.module", function="main"),
        metadata={"priority": priority, "source": "pack", "source_pack": pack_id},
    )


class TestExecutorPriorityLocalVsNonLocal:
    """Executor priority=10 (local) shadows priority=30 (non-local)."""

    def test_local_10_first_then_30(self):
        """Register local (10) first, then non-local (30) — local wins."""
        registry = ExecutorRegistry()
        registry.register(_make_exec_def("editorial.shots", priority=10, pack_id="local"))
        registry.register(_make_exec_def("editorial.shots", priority=30, pack_id="builtin"))

        winner = registry.get("editorial.shots")
        assert winner.metadata["source_pack"] == "local"
        assert winner.metadata["priority"] == 10

    def test_nonlocal_30_first_then_10(self):
        """Register non-local (30) first, then local (10) — local wins."""
        registry = ExecutorRegistry()
        registry.register(_make_exec_def("editorial.shots", priority=30, pack_id="builtin"))
        registry.register(_make_exec_def("editorial.shots", priority=10, pack_id="local"))

        winner = registry.get("editorial.shots")
        assert winner.metadata["source_pack"] == "local"
        assert winner.metadata["priority"] == 10

    def test_both_priority_30_fifo(self):
        """Two definitions with same priority — first registered wins (stable sort)."""
        registry = ExecutorRegistry()
        registry.register(_make_exec_def("editorial.shots", priority=30, pack_id="builtin"))
        registry.register(_make_exec_def("editorial.shots", priority=30, pack_id="external"))

        winner = registry.get("editorial.shots")
        # First registered wins with same priority
        assert winner.metadata["source_pack"] == "builtin"

    def test_default_priority_is_30(self):
        """Definitions without explicit priority default to 30."""
        registry = ExecutorRegistry()
        registry.register(
            ExecutorDefinition(
                id="editorial.shots",
                name="shots",
                kind="built_in",
                version="1.0.0",
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            ExecutorDefinition(
                id="editorial.shots",
                name="shots_local",
                kind="built_in",
                version="2.0.0",
                metadata={"priority": 10, "source": "pack", "source_pack": "local"},
            )
        )

        winner = registry.get("editorial.shots")
        assert winner.metadata["source_pack"] == "local"

    def test_priority_as_string_coerced_to_int(self):
        """Priority values stored as strings are coerced to int for sorting."""
        registry = ExecutorRegistry()
        # Simulate a manifest with priority as string (odd but possible)
        registry.register(
            ExecutorDefinition(
                id="editorial.shots",
                name="shots",
                kind="built_in",
                version="1.0.0",
                metadata={"priority": "5", "source": "pack", "source_pack": "local"},
            )
        )
        registry.register(
            ExecutorDefinition(
                id="editorial.shots",
                name="shots_src",
                kind="built_in",
                version="1.0.0",
                metadata={"priority": 30, "source": "pack", "source_pack": "builtin"},
            )
        )

        winner = registry.get("editorial.shots")
        assert winner.metadata["source_pack"] == "local"


class TestOrchestratorPriorityLocalVsNonLocal:
    """Orchestrator priority=10 (local) shadows priority=30 (non-local)."""

    def test_local_10_first_then_30(self):
        """Register local (10) first, then non-local (30) — local wins."""
        registry = OrchestratorRegistry()
        registry.register(_make_orch_def("video_editing.hype", priority=10, pack_id="local"))
        registry.register(_make_orch_def("video_editing.hype", priority=30, pack_id="builtin"))

        winner = registry.get("video_editing.hype")
        assert winner.metadata["source_pack"] == "local"

    def test_nonlocal_30_first_then_10(self):
        """Register non-local (30) first, then local (10) — local wins."""
        registry = OrchestratorRegistry()
        registry.register(_make_orch_def("video_editing.hype", priority=30, pack_id="builtin"))
        registry.register(_make_orch_def("video_editing.hype", priority=10, pack_id="local"))

        winner = registry.get("video_editing.hype")
        assert winner.metadata["source_pack"] == "local"

    def test_both_same_priority_stable_sort(self):
        """Same priority — first registered wins."""
        registry = OrchestratorRegistry()
        registry.register(_make_orch_def("video_editing.hype", priority=30, pack_id="builtin"))
        registry.register(_make_orch_def("video_editing.hype", priority=30, pack_id="external"))

        winner = registry.get("video_editing.hype")
        assert winner.metadata["source_pack"] == "builtin"

    def test_three_definitions_with_different_priorities(self):
        """Three definitions — lowest priority number wins."""
        registry = OrchestratorRegistry()
        registry.register(_make_orch_def("video_editing.hype", priority=50, pack_id="experimental"))
        registry.register(_make_orch_def("video_editing.hype", priority=30, pack_id="builtin"))
        registry.register(_make_orch_def("video_editing.hype", priority=10, pack_id="local"))

        winner = registry.get("video_editing.hype")
        assert winner.metadata["source_pack"] == "local"


class TestListAndAsMapping:
    """list() and as_mapping() only return winners."""

    def test_list_returns_only_winners(self):
        """list() returns one definition per id (the winner)."""
        registry = ExecutorRegistry()
        registry.register(_make_exec_def("builtin.a", priority=30, pack_id="builtin"))
        registry.register(_make_exec_def("builtin.a", priority=10, pack_id="local"))
        registry.register(_make_exec_def("builtin.b", priority=30, pack_id="builtin"))

        listed = registry.list()
        ids = [e.id for e in listed]
        assert ids.count("builtin.a") == 1
        assert ids.count("builtin.b") == 1

    def test_as_mapping_returns_winners(self):
        """as_mapping() returns the winner for each id."""
        registry = ExecutorRegistry()
        registry.register(_make_exec_def("builtin.a", priority=30, pack_id="builtin"))
        registry.register(_make_exec_def("builtin.a", priority=10, pack_id="local"))

        mapping = registry.as_mapping()
        assert mapping["builtin.a"].metadata["source_pack"] == "local"
