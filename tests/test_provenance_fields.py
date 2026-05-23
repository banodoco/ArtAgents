"""Tests for forked_from/upstream_version/compatibility_token on CapabilityHandle
across all three types (executor, orchestrator, element).

Verifies that to_capability_handle() reads fork/provenance/edit-state fields
from definition.metadata and passes them correctly to CapabilityHandle.

All definitions are constructed inline — no real registry loads.
No real LLM calls, no real network calls, no real git ops on actual repo.
"""

from __future__ import annotations

from pathlib import Path

from astrid.contracts.schema import (
    CapabilityHandle,
    LocalEditState,
    Port,
    Output,
    Provenance,
    SafetyDeclaration,
    IsolationMetadata,
    CachePolicy,
    CommandSpec,
)
from astrid.core.executor.schema import (
    ExecutorDefinition,
    GraphMetadata,
    to_capability_handle as executor_to_handle,
)
from astrid.core.orchestrator.schema import (
    OrchestratorDefinition,
    RuntimeSpec,
    to_capability_handle as orchestrator_to_handle,
)
from astrid.core.element.schema import (
    ElementDefinition,
    ElementDependencies,
    to_capability_handle as element_to_handle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_executor(**overrides) -> ExecutorDefinition:
    kwargs: dict = dict(
        id="builtin.render",
        name="Render Executor",
        kind="built_in",
        version="1.0.0",
        description="Renders video frames",
        short_description="Render frames",
        keywords=("render", "video"),
        inputs=(Port(name="input_path", type="path"),),
        outputs=(Output(name="output_path", type="path"),),
        command=CommandSpec(argv=("render.sh",)),
        cache=CachePolicy(),
        conditions=(),
        graph=GraphMetadata(depends_on=()),
        clip_kinds_supported=(),
        pipeline_requirements=(),
        isolation=IsolationMetadata(network=False),
        metadata={"source": "pack"},
        external_runtime=None,
    )
    kwargs.update(overrides)
    return ExecutorDefinition(**kwargs)


def _make_orchestrator(**overrides) -> OrchestratorDefinition:
    kwargs: dict = dict(
        id="builtin.pipeline",
        name="Pipeline Orchestrator",
        kind="built_in",
        version="2.0.0",
        runtime=RuntimeSpec(kind="python", module="astrid.pipeline", function="run"),
        description="Runs the full pipeline",
        short_description="Pipeline runner",
        keywords=("pipeline",),
        inputs=(Port(name="brief", type="string"),),
        outputs=(Output(name="result", type="json"),),
        child_executors=(),
        child_orchestrators=(),
        cache=CachePolicy(),
        isolation=IsolationMetadata(network=True),
        metadata={"source": "pack"},
    )
    kwargs.update(overrides)
    return OrchestratorDefinition(**kwargs)


def _make_element(**overrides) -> ElementDefinition:
    kwargs: dict = dict(
        id="blur",
        kind="effects",
        root=Path("/fake/pack/elements/effects/blur"),
        source="pack:builtin",
        editable=False,
        priority=30,
        component=Path("/fake/pack/elements/effects/blur/component.tsx"),
        schema={"type": "object"},
        defaults={"radius": 5},
        metadata={"name": "Gaussian Blur", "version": "1.2.0", "pack_id": "builtin"},
        dependencies=ElementDependencies(),
        description="Applies a Gaussian blur effect",
        short_description="Gaussian blur",
        keywords=("blur", "filter"),
    )
    kwargs.update(overrides)
    return ElementDefinition(**kwargs)


# ---------------------------------------------------------------------------
# Executor provenance fields
# ---------------------------------------------------------------------------


class TestExecutorProvenanceFields:
    """forked_from/upstream_version/compatibility_token on executor CapabilityHandle."""

    def test_defaults_are_none(self):
        """Without fork metadata, provenance fields are None."""
        ex = _make_executor()
        h = executor_to_handle(ex)
        assert h.provenance.forked_from is None
        assert h.provenance.upstream_version is None
        assert h.provenance.compatibility_token is None

    def test_fork_metadata_populated(self):
        """forked_from, upstream_version, compatibility_token from metadata."""
        ex = _make_executor(
            metadata={
                "source": "pack",
                "forked_from": "builtin.original_render",
                "upstream_version": "2.3.0",
                "compatibility_token": "abc123def",
            }
        )
        h = executor_to_handle(ex)
        assert h.provenance.forked_from == "builtin.original_render"
        assert h.provenance.upstream_version == "2.3.0"
        assert h.provenance.compatibility_token == "abc123def"

    def test_empty_strings_become_none(self):
        """Empty string metadata values coerce to None in Provenance."""
        ex = _make_executor(
            metadata={
                "source": "pack",
                "forked_from": "",
                "upstream_version": "",
                "compatibility_token": "",
            }
        )
        h = executor_to_handle(ex)
        assert h.provenance.forked_from is None
        assert h.provenance.upstream_version is None
        assert h.provenance.compatibility_token is None

    def test_local_edit_state_default_clean(self):
        """local_edit_state defaults to 'clean'."""
        ex = _make_executor(metadata={"source": "pack"})
        h = executor_to_handle(ex)
        assert h.local_edit_state == "clean"

    def test_local_edit_state_from_metadata(self):
        """local_edit_state is read from metadata."""
        ex = _make_executor(
            metadata={"source": "pack", "local_edit_state": "dirty"}
        )
        h = executor_to_handle(ex)
        assert h.local_edit_state == "dirty"

    def test_override_target_default_none(self):
        """override_target defaults to None."""
        ex = _make_executor(metadata={"source": "pack"})
        h = executor_to_handle(ex)
        assert h.override_target is None

    def test_override_target_from_metadata(self):
        """override_target is read from metadata."""
        ex = _make_executor(
            metadata={"source": "pack", "override_target": "local.render"}
        )
        h = executor_to_handle(ex)
        assert h.override_target == "local.render"

    def test_empty_override_target_becomes_none(self):
        """Empty string override_target coerces to None."""
        ex = _make_executor(
            metadata={"source": "pack", "override_target": ""}
        )
        h = executor_to_handle(ex)
        assert h.override_target is None


# ---------------------------------------------------------------------------
# Orchestrator provenance fields
# ---------------------------------------------------------------------------


class TestOrchestratorProvenanceFields:
    """forked_from/upstream_version/compatibility_token on orchestrator CapabilityHandle."""

    def test_defaults_are_none(self):
        orch = _make_orchestrator()
        h = orchestrator_to_handle(orch)
        assert h.provenance.forked_from is None
        assert h.provenance.upstream_version is None
        assert h.provenance.compatibility_token is None

    def test_fork_metadata_populated(self):
        orch = _make_orchestrator(
            metadata={
                "source": "pack",
                "forked_from": "builtin.original_pipeline",
                "upstream_version": "3.0.0",
                "compatibility_token": "tok123",
            }
        )
        h = orchestrator_to_handle(orch)
        assert h.provenance.forked_from == "builtin.original_pipeline"
        assert h.provenance.upstream_version == "3.0.0"
        assert h.provenance.compatibility_token == "tok123"

    def test_empty_strings_become_none(self):
        orch = _make_orchestrator(
            metadata={
                "source": "pack",
                "forked_from": "",
                "upstream_version": "",
                "compatibility_token": "",
            }
        )
        h = orchestrator_to_handle(orch)
        assert h.provenance.forked_from is None
        assert h.provenance.upstream_version is None
        assert h.provenance.compatibility_token is None

    def test_local_edit_state_and_override_target(self):
        orch = _make_orchestrator(
            metadata={
                "source": "pack",
                "local_edit_state": "conflict",
                "override_target": "local.pipeline",
            }
        )
        h = orchestrator_to_handle(orch)
        assert h.local_edit_state == "conflict"
        assert h.override_target == "local.pipeline"


# ---------------------------------------------------------------------------
# Element provenance fields
# ---------------------------------------------------------------------------


class TestElementProvenanceFields:
    """forked_from/upstream_version/compatibility_token on element CapabilityHandle."""

    def test_defaults_are_none(self):
        el = _make_element()
        h = element_to_handle(el)
        assert h.provenance.forked_from is None
        assert h.provenance.upstream_version is None
        assert h.provenance.compatibility_token is None

    def test_fork_metadata_populated(self):
        el = _make_element(
            metadata={
                "name": "Blur",
                "version": "1.0.0",
                "pack_id": "builtin",
                "forked_from": "effects/old_blur",
                "upstream_version": "0.9.0",
                "compatibility_token": "elem_tok",
            }
        )
        h = element_to_handle(el)
        assert h.provenance.forked_from == "effects/old_blur"
        assert h.provenance.upstream_version == "0.9.0"
        assert h.provenance.compatibility_token == "elem_tok"

    def test_empty_strings_become_none(self):
        el = _make_element(
            metadata={
                "name": "Blur",
                "pack_id": "builtin",
                "forked_from": "",
                "upstream_version": "",
                "compatibility_token": "",
            }
        )
        h = element_to_handle(el)
        assert h.provenance.forked_from is None
        assert h.provenance.upstream_version is None
        assert h.provenance.compatibility_token is None

    def test_local_edit_state_and_override_target(self):
        el = _make_element(
            metadata={
                "name": "Blur",
                "pack_id": "builtin",
                "local_edit_state": "dirty",
                "override_target": "local.blur",
            }
        )
        h = element_to_handle(el)
        assert h.local_edit_state == "dirty"
        assert h.override_target == "local.blur"


# ---------------------------------------------------------------------------
# Cross-adapter consistency
# ---------------------------------------------------------------------------


class TestCrossAdapterProvenanceConsistency:
    """All three adapters handle provenance fields identically."""

    def test_all_three_populate_fork_fields(self):
        """forked_from, upstream_version, compatibility_token work on all types."""
        common_meta = {
            "forked_from": "builtin.original",
            "upstream_version": "2.0.0",
            "compatibility_token": "shared_token",
        }

        ex = _make_executor(metadata={**common_meta, "source": "pack"})
        orch = _make_orchestrator(metadata={**common_meta, "source": "pack"})
        el = _make_element(metadata={**common_meta, "name": "Test", "pack_id": "builtin"})

        for h in [executor_to_handle(ex), orchestrator_to_handle(orch), element_to_handle(el)]:
            assert h.provenance.forked_from == "builtin.original"
            assert h.provenance.upstream_version == "2.0.0"
            assert h.provenance.compatibility_token == "shared_token"

    def test_all_three_default_local_edit_state_clean(self):
        """All three types default local_edit_state to 'clean'."""
        ex_h = executor_to_handle(_make_executor())
        orch_h = orchestrator_to_handle(_make_orchestrator())
        el_h = element_to_handle(_make_element())

        assert ex_h.local_edit_state == "clean"
        assert orch_h.local_edit_state == "clean"
        assert el_h.local_edit_state == "clean"

    def test_all_three_local_edit_state_valid_literal(self):
        """local_edit_state is always a valid LocalEditState literal."""
        valid_states = {"clean", "dirty", "conflict"}

        for state_str in ("clean", "dirty", "conflict"):
            meta = {"source": "pack", "local_edit_state": state_str}
            ex = _make_executor(metadata=meta)
            h = executor_to_handle(ex)
            assert h.local_edit_state in valid_states

        # Element needs name + pack_id
        for state_str in ("clean", "dirty", "conflict"):
            meta = {"name": "X", "pack_id": "builtin", "local_edit_state": state_str}
            el = _make_element(metadata=meta)
            h = element_to_handle(el)
            assert h.local_edit_state in valid_states
