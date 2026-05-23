"""Tests for AliasResolver — alias registration, resolution, cycle detection,
and orchestrator child-executor alias resolution in validation.

All tests construct AliasResolver instances inline.  No real registry loads.
tests/test_canonical_aliases.py is NOT modified.
"""

from __future__ import annotations

import pytest

from astrid.core.alias_resolver import (
    AliasResolutionError,
    AliasResolver,
    create_shared_alias_resolver,
    _register_pack_aliases,
)
from astrid.core import AliasResolver as AliasResolverFromCore
from astrid.core import AliasResolutionError as AliasResolutionErrorFromCore
from astrid.core.orchestrator.registry import OrchestratorRegistry
from astrid.core.orchestrator.schema import OrchestratorDefinition, RuntimeSpec


# ---------------------------------------------------------------------------
# SD3: import from astrid.core
# ---------------------------------------------------------------------------

class TestImportFromCore:
    """AliasResolver and AliasResolutionError export from astrid.core (SD3)."""

    def test_alias_resolver_importable_from_core(self) -> None:
        assert AliasResolverFromCore is AliasResolver

    def test_alias_resolution_error_importable_from_core(self) -> None:
        assert AliasResolutionErrorFromCore is AliasResolutionError


# ---------------------------------------------------------------------------
# Basic register / resolve
# ---------------------------------------------------------------------------

class TestBasicRegisterResolve:
    def test_register_and_resolve_single_alias(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("render", "builtin.render")
        assert resolver.resolve("render") == "builtin.render"

    def test_resolve_idempotent_for_unknown_id(self) -> None:
        resolver = AliasResolver()
        assert resolver.resolve("builtin.transcribe") == "builtin.transcribe"
        assert resolver.resolve("some.random.thing") == "some.random.thing"

    def test_is_alias_positive(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("tts", "builtin.tts")
        assert resolver.is_alias("tts") is True

    def test_is_alias_negative(self) -> None:
        resolver = AliasResolver()
        assert resolver.is_alias("builtin.tts") is False
        resolver.register_alias("tts", "builtin.tts")
        assert resolver.is_alias("builtin.tts") is False

    def test_register_empty_alias_raises(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError, match="non-empty"):
            resolver.register_alias("", "builtin.render")

    def test_register_empty_canonical_raises(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError, match="non-empty"):
            resolver.register_alias("render", "")


# ---------------------------------------------------------------------------
# Chained resolution (A -> B -> C)
# ---------------------------------------------------------------------------

class TestChainedResolution:
    def test_two_step_chain(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("B", "C")
        resolver.register_alias("A", "B")
        assert resolver.resolve("A") == "C"

    def test_multi_step_chain(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("D", "E")
        resolver.register_alias("C", "D")
        resolver.register_alias("B", "C")
        resolver.register_alias("A", "B")
        assert resolver.resolve("A") == "E"


# ---------------------------------------------------------------------------
# Cycle detection (A -> B -> A)
# ---------------------------------------------------------------------------

class TestCycleDetection:
    def test_direct_cycle_rejected(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("A", "B")
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("B", "A")

    def test_indirect_cycle_rejected(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("A", "B")
        resolver.register_alias("B", "C")
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("C", "A")

    def test_validate_no_cycles_detects_existing_cycle(self) -> None:
        """validate_no_cycles raises even if cycle pre-exists."""
        from astrid.contracts.schema import AliasRecord

        resolver = AliasResolver()
        # Manually inject a cycle by bypassing register_alias validation
        resolver._aliases["A"] = AliasRecord(
            alias="A", canonical_id="B"
        )
        resolver._aliases["B"] = AliasRecord(
            alias="B", canonical_id="A"
        )
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.validate_no_cycles()

    def test_cycle_rolls_back_state(self) -> None:
        """After a rejected cycle, the resolver state is unchanged."""
        resolver = AliasResolver()
        resolver.register_alias("A", "B")
        assert resolver.resolve("A") == "B"
        try:
            resolver.register_alias("B", "A")
        except AliasResolutionError:
            pass
        # "A" should still resolve to "B", not changed
        assert resolver.resolve("A") == "B"
        # "B" should not have been registered as an alias
        assert resolver.is_alias("B") is False


# ---------------------------------------------------------------------------
# Self-reference detection (A -> A)
# ---------------------------------------------------------------------------

class TestSelfReference:
    def test_self_reference_rejected(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("A", "A")


# ---------------------------------------------------------------------------
# Missing target validation
# ---------------------------------------------------------------------------

class TestMissingTarget:
    def test_resolve_unknown_alias_returns_unchanged(self) -> None:
        resolver = AliasResolver()
        # "nonexistent" is not a registered alias; resolve returns it as-is
        assert resolver.resolve("nonexistent") == "nonexistent"

    def test_alias_pointing_to_nonexistent_canonical_resolves(self) -> None:
        """The resolver doesn't validate that the canonical target exists —
        it only resolves aliases.  Cross-checking is the registry's job."""
        resolver = AliasResolver()
        resolver.register_alias("ghost", "pack.nonexistent")
        assert resolver.resolve("ghost") == "pack.nonexistent"


# ---------------------------------------------------------------------------
# Deprecated alias metadata
# ---------------------------------------------------------------------------

class TestDeprecatedAlias:
    def test_deprecated_alias_metadata_preserved(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias(
            "old_render",
            "builtin.render",
            deprecated=True,
            deprecation_message="Use 'builtin.render' directly",
        )
        assert resolver.resolve("old_render") == "builtin.render"
        deprecated = resolver.list_deprecated()
        assert len(deprecated) == 1
        assert deprecated[0].alias == "old_render"
        assert deprecated[0].deprecated is True
        assert deprecated[0].deprecation_message == "Use 'builtin.render' directly"

    def test_non_deprecated_alias_not_in_list(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("render", "builtin.render", deprecated=False)
        assert len(resolver.list_deprecated()) == 0


# ---------------------------------------------------------------------------
# get_aliases_for()
# ---------------------------------------------------------------------------

class TestGetAliasesFor:
    def test_get_aliases_for_returns_direct_aliases(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("r", "builtin.render")
        resolver.register_alias("rend", "builtin.render")
        resolver.register_alias("t", "builtin.transcribe")
        aliases = resolver.get_aliases_for("builtin.render")
        assert len(aliases) == 2
        alias_names = {a.alias for a in aliases}
        assert alias_names == {"r", "rend"}

    def test_get_aliases_for_empty_when_no_aliases(self) -> None:
        resolver = AliasResolver()
        assert resolver.get_aliases_for("builtin.render") == []

    def test_get_aliases_for_only_finds_direct_aliases(self) -> None:
        """Chained aliases are not returned — only the ones pointing directly
        to the canonical id."""
        resolver = AliasResolver()
        resolver.register_alias("B", "C")
        resolver.register_alias("A", "B")
        # "B" is an alias for "C", but "A" points to "B", not "C" directly
        aliases_for_C = resolver.get_aliases_for("C")
        alias_names = {a.alias for a in aliases_for_C}
        assert alias_names == {"B"}


# ---------------------------------------------------------------------------
# pack-scoped register_pack_aliases()
# ---------------------------------------------------------------------------

class TestRegisterPackAliases:
    def test_register_pack_aliases_from_dicts(self) -> None:
        resolver = AliasResolver()
        resolver.register_pack_aliases("my_pack", [
            {"alias": "rp", "canonical_id": "my_pack.render"},
            {"alias": "ap", "canonical_id": "my_pack.analyze", "deprecated": True, "deprecation_message": "old"},
        ])
        assert resolver.resolve("rp") == "my_pack.render"
        assert resolver.resolve("ap") == "my_pack.analyze"
        deprecated = resolver.list_deprecated()
        assert len(deprecated) == 1
        assert deprecated[0].alias == "ap"

    def test_register_pack_aliases_missing_alias_raises(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError, match="missing 'alias' or 'canonical_id'"):
            resolver.register_pack_aliases("pack", [{"canonical_id": "x.y"}])

    def test_register_pack_aliases_missing_canonical_raises(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError, match="missing 'alias' or 'canonical_id'"):
            resolver.register_pack_aliases("pack", [{"alias": "x"}])


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

class TestFactoryHelpers:
    def test_create_shared_alias_resolver_returns_fresh_instance(self) -> None:
        r1 = create_shared_alias_resolver()
        r2 = create_shared_alias_resolver()
        assert isinstance(r1, AliasResolver)
        assert isinstance(r2, AliasResolver)
        assert r1 is not r2  # different instances

    def test_register_pack_aliases_helper_empty_dict(self) -> None:
        resolver = AliasResolver()
        _register_pack_aliases(resolver, {})
        # No aliases added — all queries are empty
        assert resolver.list_deprecated() == []

    def test_register_pack_aliases_helper_with_data(self) -> None:
        resolver = AliasResolver()
        _register_pack_aliases(resolver, {
            "p1": [{"alias": "a1", "canonical_id": "p1.foo"}],
            "p2": [{"alias": "a2", "canonical_id": "p2.bar"}],
        })
        assert resolver.resolve("a1") == "p1.foo"
        assert resolver.resolve("a2") == "p2.bar"


# ---------------------------------------------------------------------------
# Orchestrator child-executor alias resolution in validation
# ---------------------------------------------------------------------------

def _make_minimal_orchestrator(
    id: str = "test.orch",
    *,
    child_executors: tuple[str, ...] = (),
    child_orchestrators: tuple[str, ...] = (),
) -> OrchestratorDefinition:
    return OrchestratorDefinition(
        id=id,
        name=id.split(".")[-1],
        kind="built_in",
        version="0.1.0",
        runtime=RuntimeSpec(kind="python", module="test.module", function="main"),
        child_executors=child_executors,
        child_orchestrators=child_orchestrators,
    )


class TestOrchestratorChildExecutorAliasResolution:
    """Test that OrchestratorRegistry._validate_child_executors resolves
    aliases before checking existence."""

    def test_child_executor_alias_resolved_in_validation(self) -> None:
        """An orchestrator declares a child_executor that is an alias
        pointing to an executor known to the executor registry.  Validation
        should resolve the alias and succeed.

        NOTE (SD6): child_executor IDs must contain a dot at registration
        time (per _validate_qualified_identifier).  Aliases used as
        child_executor values must therefore be dotted themselves (e.g.
        'builtin.my_alias').  The alias resolver then maps the dotted alias
        to the canonical dotted id.
        """
        from astrid.core.executor.registry import ExecutorRegistry
        from astrid.core.executor.schema import ExecutorDefinition

        exec_reg = ExecutorRegistry(alias_resolver=AliasResolver())
        exec_reg.register(ExecutorDefinition(
            id="builtin.real_exec",
            name="Real Exec",
            kind="built_in",
            version="1.0",
        ))

        resolver = AliasResolver()
        # Register a dotted alias pointing to the canonical executor
        resolver.register_alias("builtin.my_alias", "builtin.real_exec")

        orch_reg = OrchestratorRegistry(
            executor_registry=exec_reg,
            alias_resolver=resolver,
        )
        orch_reg.register(_make_minimal_orchestrator(
            id="test.orch",
            child_executors=("builtin.my_alias",),
        ))

        # Should not raise — alias "builtin.my_alias" resolves to
        # "builtin.real_exec" which IS in the executor registry.
        orch_reg.validate_all(executor_registry=exec_reg)

    def test_child_executor_alias_resolves_to_unknown_fails(self) -> None:
        """An orchestrator declares a child_executor alias that resolves
        to an unknown executor — validation should fail."""
        from astrid.core.executor.registry import ExecutorRegistry

        exec_reg = ExecutorRegistry(alias_resolver=AliasResolver())

        resolver = AliasResolver()
        resolver.register_alias("builtin.my_alias", "builtin.missing")

        orch_reg = OrchestratorRegistry(
            executor_registry=exec_reg,
            alias_resolver=resolver,
        )
        orch_reg.register(_make_minimal_orchestrator(
            id="test.orch",
            child_executors=("builtin.my_alias",),
        ))

        from astrid.core.orchestrator.registry import OrchestratorRegistryError
        with pytest.raises(OrchestratorRegistryError, match="unknown child executor"):
            orch_reg.validate_all(executor_registry=exec_reg)

    def test_child_executor_without_alias_resolver_falls_back_to_raw_id(self) -> None:
        """When no alias resolver is set, child_executor IDs are used as-is."""
        from astrid.core.executor.registry import ExecutorRegistry
        from astrid.core.executor.schema import ExecutorDefinition

        exec_reg = ExecutorRegistry()
        exec_reg.register(ExecutorDefinition(
            id="builtin.real_exec",
            name="Real Exec",
            kind="built_in",
            version="1.0",
        ))

        orch_reg = OrchestratorRegistry(executor_registry=exec_reg)
        orch_reg.register(_make_minimal_orchestrator(
            id="test.orch",
            child_executors=("builtin.real_exec",),
        ))

        orch_reg.validate_all(executor_registry=exec_reg)


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_whitespace_alias_raises(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError):
            resolver.register_alias("   ", "builtin.render")

    def test_whitespace_canonical_raises(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError):
            resolver.register_alias("r", "   ")

    def test_overwrite_alias(self) -> None:
        """Re-registering an alias overwrites the previous mapping."""
        resolver = AliasResolver()
        resolver.register_alias("r", "builtin.render")
        resolver.register_alias("r", "builtin.transcribe")
        assert resolver.resolve("r") == "builtin.transcribe"

    def test_alias_chain_to_self_via_existing(self) -> None:
        """Register B→A when A→B already exists should be rejected as cycle."""
        resolver = AliasResolver()
        resolver.register_alias("A", "B")
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("B", "A")
