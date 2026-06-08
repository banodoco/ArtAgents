"""Tests for AliasResolver — alias registration, resolution, cycle detection,
and orchestrator child-executor alias resolution in validation.

All tests construct AliasResolver instances inline.  No real registry loads.
tests/test_canonical_aliases.py is NOT modified.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from astrid.core import AliasResolutionError as AliasResolutionErrorFromCore
from astrid.core import AliasResolver as AliasResolverFromCore
from astrid.core.alias_resolver import (
    AliasResolutionError,
    AliasResolver,
    _register_pack_aliases,
    create_shared_alias_resolver,
    extract_pack_aliases,
)
from astrid.core.executor.registry import ExecutorRegistry
from astrid.core.executor.registry import load_default_registry as load_executor_registry
from astrid.core.executor.schema import ExecutorDefinition, to_capability_handle
from astrid.core.orchestrator.registry import OrchestratorRegistry, OrchestratorRegistryError
from astrid.core.orchestrator.registry import load_default_registry as load_orchestrator_registry
from astrid.core.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.core.orchestrator.schema import to_capability_handle as orch_to_capability_handle
from astrid.core.override import OverrideStore
from astrid.core.pack import PackDefinition, discover_packs

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
        resolver.register_alias("render", "rendering.render")
        assert resolver.resolve("render") == "rendering.render"

    def test_resolve_idempotent_for_unknown_id(self) -> None:
        resolver = AliasResolver()
        assert resolver.resolve("editorial.transcribe") == "editorial.transcribe"
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
            resolver.register_alias("", "rendering.render")

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
            "rendering.render",
            deprecated=True,
            deprecation_message="Use 'rendering.render' directly",
        )
        assert resolver.resolve("old_render") == "rendering.render"
        deprecated = resolver.list_deprecated()
        assert len(deprecated) == 1
        assert deprecated[0].alias == "old_render"
        assert deprecated[0].deprecated is True
        assert deprecated[0].deprecation_message == "Use 'rendering.render' directly"

    def test_non_deprecated_alias_not_in_list(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("render", "rendering.render", deprecated=False)
        assert len(resolver.list_deprecated()) == 0


# ---------------------------------------------------------------------------
# get_aliases_for()
# ---------------------------------------------------------------------------

class TestGetAliasesFor:
    def test_get_aliases_for_returns_direct_aliases(self) -> None:
        resolver = AliasResolver()
        resolver.register_alias("r", "rendering.render")
        resolver.register_alias("rend", "rendering.render")
        resolver.register_alias("t", "editorial.transcribe")
        aliases = resolver.get_aliases_for("rendering.render")
        assert len(aliases) == 2
        alias_names = {a.alias for a in aliases}
        assert alias_names == {"r", "rend"}

    def test_get_aliases_for_empty_when_no_aliases(self) -> None:
        resolver = AliasResolver()
        assert resolver.get_aliases_for("rendering.render") == []

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

    def test_register_pack_aliases_preserves_source_pack_metadata(self) -> None:
        resolver = AliasResolver()
        resolver.register_pack_aliases(
            "my_pack",
            [{"alias": "rp", "canonical_id": "my_pack.render", "deprecated": True}],
        )
        record = resolver.get_aliases_for("my_pack.render")[0]
        assert record.source_pack_id == "my_pack"
        assert record.deprecated is True


class TestExtractPackAliases:
    def test_extract_pack_aliases_filters_by_kind_and_keeps_metadata(self) -> None:
        pack = PackDefinition(
            id="builtin",
            name="Builtin",
            version="1.0.0",
            root=Path("/tmp/builtin"),
            manifest_path=Path("/tmp/builtin/pack.yaml"),
            metadata={},
            aliases=(
                {
                    "kind": "executor",
                    "alias": "builtin.old_render",
                    "canonical_id": "rendering.render",
                    "deprecated": True,
                    "deprecation_message": "Use rendering.render",
                },
                {
                    "kind": "orchestrator",
                    "alias": "builtin.old_hype",
                    "canonical_id": "video_editing.hype",
                },
            ),
        )

        executor_aliases = extract_pack_aliases((pack,), kind="executor")
        orchestrator_aliases = extract_pack_aliases((pack,), kind="orchestrator")

        assert list(executor_aliases) == ["builtin"]
        assert executor_aliases["builtin"][0]["alias"] == "builtin.old_render"
        assert executor_aliases["builtin"][0]["deprecated"] is True
        assert executor_aliases["builtin"][0]["deprecation_message"] == "Use rendering.render"
        assert executor_aliases["builtin"][0]["source_pack_id"] == "builtin"
        assert list(orchestrator_aliases) == ["builtin"]
        assert orchestrator_aliases["builtin"][0]["alias"] == "builtin.old_hype"


def _write_pack(root: Path, pack_id: str, aliases: str = "") -> Path:
    pack_root = root / pack_id
    pack_root.mkdir(parents=True)
    pack_yaml = [
        "schema_version: 1",
        f"id: {pack_id}",
        f"name: {pack_id.title()} Pack",
        "version: '1.0'",
    ]
    if aliases:
        pack_yaml.append("aliases:")
        pack_yaml.extend(aliases.splitlines())
    (pack_root / "pack.yaml").write_text("\n".join(pack_yaml) + "\n", encoding="utf-8")
    return pack_root


def _write_executor(root: Path, folder: str, executor_id: str) -> None:
    executor_root = root / folder
    executor_root.mkdir()
    (executor_root / "executor.yaml").write_text(
        "\n".join(
            [
                f"id: {executor_id}",
                f"name: {executor_id}",
                "kind: built_in",
                "version: '1.0'",
                "command:",
                "  argv: ['echo', 'ok']",
                "cache:",
                "  mode: none",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_orchestrator(root: Path, folder: str, orchestrator_id: str) -> None:
    orchestrator_root = root / folder
    orchestrator_root.mkdir()
    (orchestrator_root / "orchestrator.yaml").write_text(
        "\n".join(
            [
                f"id: {orchestrator_id}",
                f"name: {orchestrator_id}",
                "kind: built_in",
                "version: '1.0'",
                "runtime:",
                "  kind: command",
                "  command:",
                "    argv: ['echo', 'ok']",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


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
# Default registry alias loading from pack manifests
# ---------------------------------------------------------------------------

class TestDefaultRegistryPackAliasLoading:
    def test_executor_default_registry_loads_only_executor_pack_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "rendering",
                aliases="\n".join(
                    [
                        "  - kind: executor",
                        "    alias: builtin.legacy_render",
                        "    canonical_id: rendering.render",
                        "    deprecated: true",
                        "    deprecation_message: use rendering.render",
                        "  - kind: orchestrator",
                        "    alias: builtin.legacy_hype",
                        "    canonical_id: video_editing.hype",
                    ]
                ),
            )
            _write_executor(pack_root, "render", "rendering.render")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

        assert registry.alias_resolver is not None
        assert registry.alias_resolver.resolve("builtin.legacy_render") == "rendering.render"
        assert registry.alias_resolver.is_alias("builtin.legacy_hype") is False
        aliases = registry.alias_resolver.get_aliases_for("rendering.render")
        assert len(aliases) == 1
        assert aliases[0].source_pack_id == "rendering"
        assert aliases[0].deprecated is True
        assert aliases[0].deprecation_message == "use rendering.render"

    def test_orchestrator_default_registry_loads_only_orchestrator_pack_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "video_editing",
                aliases="\n".join(
                    [
                        "  - kind: executor",
                        "    alias: builtin.legacy_render",
                        "    canonical_id: rendering.render",
                        "  - kind: orchestrator",
                        "    alias: builtin.legacy_hype",
                        "    canonical_id: video_editing.hype",
                        "    deprecated: true",
                        "    deprecation_message: use video_editing.hype",
                    ]
                ),
            )
            _write_orchestrator(pack_root, "hype", "video_editing.hype")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                registry = load_orchestrator_registry()

        assert registry.alias_resolver is not None
        assert registry.alias_resolver.resolve("builtin.legacy_hype") == "video_editing.hype"
        assert registry.alias_resolver.is_alias("builtin.legacy_render") is False
        aliases = registry.alias_resolver.get_aliases_for("video_editing.hype")
        assert len(aliases) == 1
        assert aliases[0].source_pack_id == "video_editing"
        assert aliases[0].deprecated is True
        assert aliases[0].deprecation_message == "use video_editing.hype"


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
            resolver.register_alias("   ", "rendering.render")

    def test_whitespace_canonical_raises(self) -> None:
        resolver = AliasResolver()
        with pytest.raises(AliasResolutionError):
            resolver.register_alias("r", "   ")

    def test_overwrite_alias(self) -> None:
        """Re-registering an alias overwrites the previous mapping."""
        resolver = AliasResolver()
        resolver.register_alias("r", "rendering.render")
        resolver.register_alias("r", "editorial.transcribe")
        assert resolver.resolve("r") == "editorial.transcribe"

    def test_alias_chain_to_self_via_existing(self) -> None:
        """Register B→A when A→B already exists should be rejected as cycle."""
        resolver = AliasResolver()
        resolver.register_alias("A", "B")
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("B", "A")


# ---------------------------------------------------------------------------
# Executor graph.depends_on alias resolution (integration)
# ---------------------------------------------------------------------------

class TestExecutorDependsOnAliasResolution:
    """Tests that ExecutorRegistry._validate_graph_references resolves
    aliases in graph.depends_on before checking existence."""

    def test_depends_on_alias_resolves_to_known_executor(self) -> None:
        """Executor A depends on alias 'test.dep_alias' which maps to 'test.b'.
        Validation should resolve the alias and succeed."""
        from astrid.core.executor.registry import ExecutorRegistry
        from astrid.core.executor.schema import GraphMetadata

        resolver = AliasResolver()
        resolver.register_alias("test.dep_alias", "test.b")

        registry = ExecutorRegistry(alias_resolver=resolver)
        registry.register(ExecutorDefinition(
            id="test.a",
            name="A",
            kind="built_in",
            version="1.0",
            graph=GraphMetadata(depends_on=("test.dep_alias",)),
        ))
        registry.register(ExecutorDefinition(
            id="test.b",
            name="B",
            kind="built_in",
            version="1.0",
        ))

        # Should not raise
        registry.validate_all()

    def test_depends_on_alias_resolves_to_unknown_executor_fails(self) -> None:
        """Executor A depends on alias 'test.dep_alias' which maps to
        an executor not in the registry. Validation should fail."""
        from astrid.core.executor.registry import ExecutorRegistry, ExecutorRegistryError
        from astrid.core.executor.schema import GraphMetadata

        resolver = AliasResolver()
        resolver.register_alias("test.dep_alias", "test.missing")

        registry = ExecutorRegistry(alias_resolver=resolver)
        registry.register(ExecutorDefinition(
            id="test.a",
            name="A",
            kind="built_in",
            version="1.0",
            graph=GraphMetadata(depends_on=("test.dep_alias",)),
        ))

        with pytest.raises(ExecutorRegistryError, match="depends on unknown executor"):
            registry.validate_all()

    def test_depends_on_alias_chained_resolves_correctly(self) -> None:
        """Executor A depends on 'test.chain_a' → 'test.chain_b' → 'test.c'.
        Validation should resolve the chain and succeed."""
        from astrid.core.executor.registry import ExecutorRegistry
        from astrid.core.executor.schema import GraphMetadata

        resolver = AliasResolver()
        resolver.register_alias("test.chain_a", "test.chain_b")
        resolver.register_alias("test.chain_b", "test.c")

        registry = ExecutorRegistry(alias_resolver=resolver)
        registry.register(ExecutorDefinition(
            id="test.a",
            name="A",
            kind="built_in",
            version="1.0",
            graph=GraphMetadata(depends_on=("test.chain_a",)),
        ))
        registry.register(ExecutorDefinition(
            id="test.c",
            name="C",
            kind="built_in",
            version="1.0",
        ))

        registry.validate_all()

    def test_depends_on_without_alias_resolver_falls_back_to_raw_id(self) -> None:
        """When no alias resolver is set, depends_on IDs are used as-is."""
        from astrid.core.executor.registry import ExecutorRegistry
        from astrid.core.executor.schema import GraphMetadata

        registry = ExecutorRegistry()
        registry.register(ExecutorDefinition(
            id="test.a",
            name="A",
            kind="built_in",
            version="1.0",
            graph=GraphMetadata(depends_on=("test.b",)),
        ))
        registry.register(ExecutorDefinition(
            id="test.b",
            name="B",
            kind="built_in",
            version="1.0",
        ))

        registry.validate_all()

    def test_depends_on_self_reference_via_alias_fails(self) -> None:
        """Executor A depends on alias 'test.self_alias' which maps to 'test.a'.
        Validation should detect the self-reference."""
        from astrid.core.executor.registry import ExecutorRegistry, ExecutorRegistryError
        from astrid.core.executor.schema import GraphMetadata

        resolver = AliasResolver()
        resolver.register_alias("test.self_alias", "test.a")

        registry = ExecutorRegistry(alias_resolver=resolver)
        registry.register(ExecutorDefinition(
            id="test.a",
            name="A",
            kind="built_in",
            version="1.0",
            graph=GraphMetadata(depends_on=("test.self_alias",)),
        ))

        with pytest.raises(ExecutorRegistryError, match="cannot depend on itself"):
            registry.validate_all()


# ---------------------------------------------------------------------------
# Orchestrator child_orchestrators alias resolution (integration)
# ---------------------------------------------------------------------------

class TestOrchestratorChildOrchestratorAliasResolution:
    """Tests that OrchestratorRegistry._validate_child_orchestrators
    resolves aliases in child_orchestrators before checking existence."""

    def test_child_orchestrator_alias_resolves_to_known_orchestrator(self) -> None:
        """Orchestrator A declares child orchestrator alias 'test.child_alias'
        which maps to 'test.b'. Validation should succeed."""
        from astrid.core.executor.registry import ExecutorRegistry

        resolver = AliasResolver()
        resolver.register_alias("test.child_alias", "test.b")

        orch_reg = OrchestratorRegistry(
            executor_registry=ExecutorRegistry(),
            alias_resolver=resolver,
        )
        orch_reg.register(_make_minimal_orchestrator(
            id="test.a",
            child_orchestrators=("test.child_alias",),
        ))
        orch_reg.register(_make_minimal_orchestrator(
            id="test.b",
        ))

        orch_reg.validate_all(executor_registry=ExecutorRegistry())

    def test_child_orchestrator_alias_resolves_to_unknown_fails(self) -> None:
        """Orchestrator A declares child orchestrator alias that maps to
        an unknown orchestrator. Validation should fail."""
        from astrid.core.executor.registry import ExecutorRegistry

        resolver = AliasResolver()
        resolver.register_alias("test.child_alias", "test.missing")

        orch_reg = OrchestratorRegistry(
            executor_registry=ExecutorRegistry(),
            alias_resolver=resolver,
        )
        orch_reg.register(_make_minimal_orchestrator(
            id="test.a",
            child_orchestrators=("test.child_alias",),
        ))

        with pytest.raises(OrchestratorRegistryError, match="unknown child orchestrator"):
            orch_reg.validate_all(executor_registry=ExecutorRegistry())

    def test_child_orchestrator_alias_chained_resolves_correctly(self) -> None:
        """Orchestrator A → alias chain → test.c. Validation should succeed."""
        from astrid.core.executor.registry import ExecutorRegistry

        resolver = AliasResolver()
        resolver.register_alias("test.chain_a", "test.chain_b")
        resolver.register_alias("test.chain_b", "test.c")

        orch_reg = OrchestratorRegistry(
            executor_registry=ExecutorRegistry(),
            alias_resolver=resolver,
        )
        orch_reg.register(_make_minimal_orchestrator(
            id="test.a",
            child_orchestrators=("test.chain_a",),
        ))
        orch_reg.register(_make_minimal_orchestrator(
            id="test.c",
        ))

        orch_reg.validate_all(executor_registry=ExecutorRegistry())

    def test_child_orchestrator_self_reference_via_alias_fails(self) -> None:
        """Orchestrator A declares child orchestrator alias that maps to
        test.a itself. Validation should detect the self-reference."""
        from astrid.core.executor.registry import ExecutorRegistry

        resolver = AliasResolver()
        resolver.register_alias("test.self_alias", "test.a")

        orch_reg = OrchestratorRegistry(
            executor_registry=ExecutorRegistry(),
            alias_resolver=resolver,
        )
        orch_reg.register(_make_minimal_orchestrator(
            id="test.a",
            child_orchestrators=("test.self_alias",),
        ))

        with pytest.raises(OrchestratorRegistryError, match="cannot reference itself"):
            orch_reg.validate_all(executor_registry=ExecutorRegistry())

    def test_child_orchestrator_without_alias_resolver_falls_back_to_raw_id(self) -> None:
        """When no alias resolver is set, child_orchestrator IDs are used as-is."""
        from astrid.core.executor.registry import ExecutorRegistry

        orch_reg = OrchestratorRegistry(executor_registry=ExecutorRegistry())
        orch_reg.register(_make_minimal_orchestrator(
            id="test.a",
            child_orchestrators=("test.b",),
        ))
        orch_reg.register(_make_minimal_orchestrator(
            id="test.b",
        ))

        orch_reg.validate_all(executor_registry=ExecutorRegistry())

    def test_child_orchestrator_alias_cycle_detected(self) -> None:
        """A → alias(B) → B → alias(A) should detect a cycle across aliases."""
        from astrid.core.executor.registry import ExecutorRegistry

        resolver = AliasResolver()
        resolver.register_alias("test.alias_a", "test.a")
        resolver.register_alias("test.alias_b", "test.b")

        orch_reg = OrchestratorRegistry(
            executor_registry=ExecutorRegistry(),
            alias_resolver=resolver,
        )
        orch_reg.register(_make_minimal_orchestrator(
            id="test.a",
            child_orchestrators=("test.alias_b",),
        ))
        orch_reg.register(_make_minimal_orchestrator(
            id="test.b",
            child_orchestrators=("test.alias_a",),
        ))

        with pytest.raises(OrchestratorRegistryError, match="cycle"):
            orch_reg.validate_all(executor_registry=ExecutorRegistry())


# ---------------------------------------------------------------------------
# Temp-pack manifest integration: pack.yaml aliases → registry loading
# ---------------------------------------------------------------------------

class TestTempPackAliasIntegration:
    """Full integration tests that create temp packs with pack.yaml aliases,
    executor.yaml / orchestrator.yaml manifests, then load default registries
    and verify alias resolution, override behavior, and missing-target errors."""

    def test_pack_yaml_aliases_flow_into_executor_registry_lookup(self) -> None:
        """Create a temp pack with pack.yaml aliases (kind: executor) and an
        executor.yaml. Load the executor registry and verify:
        - alias resolves to the canonical executor
        - get() via the alias returns the canonical definition
        - get() via the canonical id also works
        - alias metadata (deprecated, deprecation_message) is preserved
        """
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "testpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: testpack.old_runner",
                    "    canonical_id: testpack.runner",
                    "    deprecated: true",
                    "    deprecation_message: Use testpack.runner instead",
                    "  - kind: orchestrator",
                    "    alias: testpack.old_flow",
                    "    canonical_id: testpack.flow",
                ]),
            )
            _write_executor(pack_root, "runner", "testpack.runner")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            # Direct lookup via canonical id
            canonical = registry.get("testpack.runner")
            assert canonical.id == "testpack.runner"

            # Alias lookup
            aliased = registry.get("testpack.old_runner")
            assert aliased.id == "testpack.runner"

            # Alias metadata: enrich handle via resolver (same pattern as CLI _cmd_inspect)
            handle = to_capability_handle(aliased)
            resolver = registry.alias_resolver
            assert resolver is not None
            handle_aliases = resolver.get_aliases_for(aliased.id)
            assert len(handle_aliases) == 1
            assert handle_aliases[0].alias == "testpack.old_runner"
            assert handle_aliases[0].deprecated is True
            assert handle_aliases[0].deprecation_message == "Use testpack.runner instead"

            # Orchestrator aliases should NOT be in the executor resolver
            assert registry.alias_resolver.is_alias("testpack.old_flow") is False

    def test_pack_yaml_aliases_flow_into_orchestrator_registry_lookup(self) -> None:
        """Create a temp pack with pack.yaml aliases (kind: orchestrator) and an
        orchestrator.yaml. Load the orchestrator registry and verify alias
        resolution and metadata preservation."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "testpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: testpack.old_runner",
                    "    canonical_id: testpack.runner",
                    "  - kind: orchestrator",
                    "    alias: testpack.old_flow",
                    "    canonical_id: testpack.flow",
                    "    deprecated: true",
                    "    deprecation_message: Use testpack.flow instead",
                ]),
            )
            _write_orchestrator(pack_root, "flow", "testpack.flow")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                registry = load_orchestrator_registry()

            # Direct lookup via canonical id
            canonical = registry.get("testpack.flow")
            assert canonical.id == "testpack.flow"

            # Alias lookup
            aliased = registry.get("testpack.old_flow")
            assert aliased.id == "testpack.flow"

            # Alias metadata: enrich handle via resolver (same pattern as CLI _cmd_inspect)
            handle = orch_to_capability_handle(aliased)
            resolver = registry.alias_resolver
            assert resolver is not None
            handle_aliases = resolver.get_aliases_for(aliased.id)
            assert len(handle_aliases) == 1
            assert handle_aliases[0].alias == "testpack.old_flow"
            assert handle_aliases[0].deprecated is True

            # Executor aliases should NOT be in the orchestrator resolver
            assert registry.alias_resolver is not None
            assert registry.alias_resolver.is_alias("testpack.old_runner") is False

    def test_pack_yaml_alias_missing_canonical_target_raises_on_get(self) -> None:
        """Pack declares an executor alias whose canonical_id does not exist
        in the registry. get() via the alias should raise KeyError.
        
        We bypass load_default_registry (which calls validate_all) and
        construct a registry manually so we can test get() semantics directly."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            _write_pack(
                packs_root,
                "testpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: testpack.ghost",
                    "    canonical_id: testpack.nonexistent",
                ]),
            )
            # Note: no executor.yaml for testpack.nonexistent
            packs = discover_packs(packs_root)

            # Manually build a registry with the pack aliases but skip validate_all
            resolver = AliasResolver()
            _register_pack_aliases(resolver, extract_pack_aliases(packs, kind="executor"))
            registry = ExecutorRegistry(alias_resolver=resolver)

            with pytest.raises(KeyError, match="alias.*points to missing executor"):
                registry.get("testpack.ghost")

    def test_pack_yaml_alias_with_override_resolves_override_target(self) -> None:
        """Pack declares an executor alias to canonical A. Override maps
        canonical A → B. get() via alias should return B's definition."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "testpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: testpack.old_runner",
                    "    canonical_id: testpack.runner",
                ]),
            )
            _write_executor(pack_root, "runner", "testpack.runner")
            # Also add a local-like executor to simulate override target
            local_root = packs_root / "local"
            local_root.mkdir(parents=True, exist_ok=True)
            _write_executor(local_root, "runner", "local.runner")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            # Manually register the override target (since it may not be
            # auto-discovered in this temp structure)
            from astrid.core.executor.schema import ExecutorDefinition
            registry.register(ExecutorDefinition(
                id="local.runner",
                name="Local Runner",
                kind="built_in",
                version="2.0",
                metadata={"source": "pack", "source_pack": "local"},
            ))

            # Set override: testpack.runner → local.runner
            override_store = OverrideStore(project_root=tmp)
            override_store.set_override("executor", "testpack.runner", "local.runner")
            registry.override_store = override_store

            # Alias lookup should resolve: alias → canonical → override
            result = registry.get("testpack.old_runner")
            assert result.id == "local.runner"
            assert result.name == "Local Runner"

    def test_pack_yaml_both_kinds_with_executor_and_orchestrator_in_same_pack(self) -> None:
        """A single pack declares both executor and orchestrator aliases
        alongside both executor.yaml and orchestrator.yaml. Both registries
        should load only their respective kind-filtered aliases."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "dualpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: dualpack.old_run",
                    "    canonical_id: dualpack.run",
                    "  - kind: orchestrator",
                    "    alias: dualpack.old_flow",
                    "    canonical_id: dualpack.flow",
                ]),
            )
            _write_executor(pack_root, "run", "dualpack.run")
            _write_orchestrator(pack_root, "flow", "dualpack.flow")
            packs = discover_packs(packs_root)

            # Load executor registry
            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                exec_reg = load_executor_registry()
            assert exec_reg.alias_resolver.resolve("dualpack.old_run") == "dualpack.run"
            assert not exec_reg.alias_resolver.is_alias("dualpack.old_flow")

            # Load orchestrator registry
            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                orch_reg = load_orchestrator_registry()
            assert orch_reg.alias_resolver.resolve("dualpack.old_flow") == "dualpack.flow"
            assert not orch_reg.alias_resolver.is_alias("dualpack.old_run")

    def test_pack_yaml_aliases_preserve_source_pack_id_in_handle(self) -> None:
        """Verify that source_pack_id is carried through from pack.yaml alias
        declarations into the resolver records."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "srcpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: srcpack.legacy",
                    "    canonical_id: srcpack.main",
                ]),
            )
            _write_executor(pack_root, "main", "srcpack.main")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            result = registry.get("srcpack.legacy")
            assert result.id == "srcpack.main"
            # The source_pack_id is stored in the resolver record
            assert registry.alias_resolver is not None
            resolver_aliases = registry.alias_resolver.get_aliases_for("srcpack.main")
            assert len(resolver_aliases) == 1
            assert resolver_aliases[0].source_pack_id == "srcpack"

    def test_pack_yaml_alias_to_alias_chain_in_same_pack(self) -> None:
        """Pack declares alias A→B and B→C. Loading through pack.yaml should
        register both and resolve A to C through the chain."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "chainpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: chainpack.v1",
                    "    canonical_id: chainpack.v2",
                    "  - kind: executor",
                    "    alias: chainpack.v2",
                    "    canonical_id: chainpack.v3",
                ]),
            )
            _write_executor(pack_root, "v3", "chainpack.v3")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            # v1 → v2 → v3
            result = registry.get("chainpack.v1")
            assert result.id == "chainpack.v3"

    def test_pack_yaml_empty_aliases_still_loads_registry(self) -> None:
        """Pack with no aliases declared should still load normally without
        breaking the registry."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(packs_root, "cleanpack")
            _write_executor(pack_root, "main", "cleanpack.main")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            result = registry.get("cleanpack.main")
            assert result.id == "cleanpack.main"
            # Should still have an empty alias resolver
            assert registry.alias_resolver is not None
            assert len(registry.alias_resolver._aliases) == 0


# ---------------------------------------------------------------------------
# T10: Search alias visibility — aliases field in search records
# ---------------------------------------------------------------------------


class TestAliasSearchRecords:
    """Search record builders include alias ids in the fields dict so that
    alias terms score against canonical capabilities without duplicate hits."""

    def test_executor_search_record_includes_alias_field(self) -> None:
        """_executor_search_record puts alias text into fields['aliases']."""
        from astrid.core.executor.cli import _executor_search_record

        definition = ExecutorDefinition(
            id="testpack.runner",
            name="Runner",
            kind="built_in",
            version="1.0",
            command={"argv": ["echo", "ok"]},
            cache={"mode": "none"},
        )
        record = _executor_search_record(definition, aliases="testpack.old_runner [deprecated] Use testpack.runner")
        assert record.fields.get("aliases") == "testpack.old_runner [deprecated] Use testpack.runner"

    def test_executor_search_record_omits_aliases_when_empty(self) -> None:
        """_executor_search_record does not include 'aliases' key when empty."""
        from astrid.core.executor.cli import _executor_search_record

        definition = ExecutorDefinition(
            id="testpack.runner",
            name="Runner",
            kind="built_in",
            version="1.0",
            command={"argv": ["echo", "ok"]},
            cache={"mode": "none"},
        )
        record = _executor_search_record(definition)  # default aliases=""
        assert "aliases" not in record.fields

    def test_orchestrator_search_record_includes_alias_field(self) -> None:
        """_orchestrator_search_record puts alias text into fields['aliases']."""
        from astrid.core.orchestrator.cli import _orchestrator_search_record
        from astrid.core.orchestrator.schema import OrchestratorDefinition, RuntimeSpec

        definition = OrchestratorDefinition(
            id="testpack.flow",
            name="Flow",
            kind="built_in",
            version="1.0",
            runtime=RuntimeSpec(kind="command", command={"command": ["echo", "ok"]}),
        )
        record = _orchestrator_search_record(definition, aliases="testpack.old_flow [deprecated] Use testpack.flow")
        assert record.fields.get("aliases") == "testpack.old_flow [deprecated] Use testpack.flow"

    def test_search_scoring_matches_alias_field(self) -> None:
        """search() matches terms found in the 'aliases' field of a record."""
        from astrid.core.search import FIELD_WEIGHTS, SearchRecord, search

        assert "aliases" in FIELD_WEIGHTS
        assert FIELD_WEIGHTS["aliases"] == 3.0

        record = SearchRecord(
            id="testpack.runner",
            kind="executor",
            short_description="A runner",
            fields={
                "id": "testpack.runner",
                "name": "Runner",
                "short_description": "A runner",
                "description": "Does stuff",
                "keywords": "run execute",
                "aliases": "testpack.old_runner [deprecated] Use testpack.runner instead",
            },
        )

        # Searching by the alias id should find the canonical record
        hits = search([record], ["old_runner"])
        assert len(hits) == 1
        assert hits[0].record.id == "testpack.runner"
        assert hits[0].score > 0

    def test_search_alias_does_not_produce_duplicate_hits(self) -> None:
        """Searching by an alias term returns exactly one hit — the canonical
        capability, not a separate alias record."""
        from astrid.core.search import SearchRecord, search

        canonical = SearchRecord(
            id="testpack.runner",
            kind="executor",
            short_description="A runner",
            fields={
                "id": "testpack.runner",
                "name": "Runner",
                "short_description": "A runner",
                "description": "Does things",
                "keywords": "run execute",
                "aliases": "testpack.old_runner",
            },
        )

        # No separate alias record is emitted
        hits = search([canonical], ["old_runner"])
        assert len(hits) == 1
        assert hits[0].record.id == "testpack.runner"


class TestSearchAliasIntegration:
    """Integration: temp pack with aliases → registry → search records."""

    def test_pack_yaml_aliases_appear_in_executor_search_record_fields(self) -> None:
        """Create a temp pack with an executor alias, load the registry, and
        verify the alias id appears in the search record fields['aliases']."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "testpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: testpack.old_runner",
                    "    canonical_id: testpack.runner",
                    "    deprecated: true",
                    "    deprecation_message: Use testpack.runner instead",
                ]),
            )
            _write_executor(pack_root, "runner", "testpack.runner")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            from astrid.core.executor.cli import _aliases_text, _executor_search_record

            resolver = registry.alias_resolver
            assert resolver is not None

            for executor in registry.list():
                aliases = _aliases_text(resolver, executor.id)
                record = _executor_search_record(executor, aliases=aliases)
                if executor.id == "testpack.runner":
                    assert "aliases" in record.fields
                    assert "testpack.old_runner" in record.fields["aliases"]
                    assert "[deprecated]" in record.fields["aliases"]
                    assert "Use testpack.runner instead" in record.fields["aliases"]
                else:
                    # Other executors should not have the old_runner alias
                    assert "testpack.old_runner" not in record.fields.get("aliases", "")

    def test_pack_yaml_aliases_appear_in_orchestrator_search_record_fields(self) -> None:
        """Create a temp pack with an orchestrator alias, load the registry, and
        verify the alias id appears in the search record fields['aliases']."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "testpack",
                aliases="\n".join([
                    "  - kind: orchestrator",
                    "    alias: testpack.old_flow",
                    "    canonical_id: testpack.flow",
                    "    deprecated: true",
                    "    deprecation_message: Use testpack.flow instead",
                ]),
            )
            _write_orchestrator(pack_root, "flow", "testpack.flow")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                registry = load_orchestrator_registry()

            from astrid.core.orchestrator.cli import _aliases_text, _orchestrator_search_record

            resolver = registry.alias_resolver
            assert resolver is not None

            for orchestrator in registry.list():
                aliases = _aliases_text(resolver, orchestrator.id)
                record = _orchestrator_search_record(orchestrator, aliases=aliases)
                if orchestrator.id == "testpack.flow":
                    assert "aliases" in record.fields
                    assert "testpack.old_flow" in record.fields["aliases"]
                    assert "[deprecated]" in record.fields["aliases"]
                    assert "Use testpack.flow instead" in record.fields["aliases"]
                else:
                    # Other orchestrators should not have the old_flow alias
                    assert "testpack.old_flow" not in record.fields.get("aliases", "")

    def test_search_by_alias_returns_canonical_no_duplicates(self) -> None:
        """End-to-end: temp pack with alias → load registry → search by alias
        via _cmd_search → single canonical hit, no duplicate."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = _write_pack(
                packs_root,
                "testpack",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: testpack.old_runner",
                    "    canonical_id: testpack.runner",
                ]),
            )
            _write_executor(pack_root, "runner", "testpack.runner")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            # Build search records using the same logic as _cmd_search
            from astrid.core.executor.cli import _aliases_text, _executor_search_record
            from astrid.core.search import search as run_search

            resolver = registry.alias_resolver
            assert resolver is not None

            records = [
                _executor_search_record(
                    executor,
                    aliases=_aliases_text(resolver, executor.id),
                )
                for executor in registry.list()
            ]

            # Search by the alias — should return the canonical capability
            hits = run_search(records, ["old_runner"])
            assert len(hits) == 1
            assert hits[0].record.id == "testpack.runner"

            # Search by canonical id should also work
            hits2 = run_search(records, ["testpack.runner"])
            assert len(hits2) >= 1
            assert any(h.record.id == "testpack.runner" for h in hits2)


# ---------------------------------------------------------------------------
# T11: Representative migrated-pack fixtures — deprecated old ids that
# resolve to new canonical ids via pack.yaml aliases.  These temp-pack
# tests prove the migration path (rendering.render → rendering.render,
# vibecomfy.run → vibecomfy.run, etc.) without moving any real
# source-tree capability files.
# ---------------------------------------------------------------------------


class TestMigratedPackAliasFixtures:
    """T11: Temp-pack fixtures for representative canonical ids and their
    deprecated aliases.  Covers registry lookup, CLI inspect JSON, and
    human-readable inspect output — all using temporary directories, so
    no real ``builtin``, ``external``, or ``upload`` files are touched.
    """

    # -- helpers (largely mirror the module-level helpers but let us
    #    keep the new test class self-contained) --------------------------

    @staticmethod
    def _write_pack(root: Path, pack_id: str, aliases: str = "") -> Path:
        pack_root = root / pack_id
        pack_root.mkdir(parents=True)
        lines = [
            "schema_version: 1",
            f"id: {pack_id}",
            f"name: {pack_id.title()} Pack",
            "version: '1.0'",
        ]
        if aliases:
            lines.append("aliases:")
            lines.extend(aliases.splitlines())
        (pack_root / "pack.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return pack_root

    @staticmethod
    def _write_executor(pack_root: Path, folder: str, executor_id: str) -> None:
        root = pack_root / folder
        root.mkdir()
        (root / "executor.yaml").write_text(
            "\n".join([
                f"id: {executor_id}",
                f"name: {executor_id}",
                "kind: built_in",
                "version: '1.0'",
                "command:",
                "  argv: ['echo', 'ok']",
                "cache:",
                "  mode: none",
            ]) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_orchestrator(pack_root: Path, folder: str, orch_id: str) -> None:
        root = pack_root / folder
        root.mkdir()
        (root / "orchestrator.yaml").write_text(
            "\n".join([
                f"id: {orch_id}",
                f"name: {orch_id}",
                "kind: built_in",
                "version: '1.0'",
                "runtime:",
                "  kind: command",
                "  command:",
                "    argv: ['echo', 'ok']",
            ]) + "\n",
            encoding="utf-8",
        )

    # -- registry lookup via deprecated alias -----------------------------

    def test_deprecated_alias_builtin_render_resolves_to_rendering_render(self) -> None:
        """``rendering.render`` (deprecated) → ``rendering.render`` (canonical)."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "rendering",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: builtin.render",
                    "    canonical_id: rendering.render",
                    "    deprecated: true",
                    "    deprecation_message: Moved to rendering.render",
                ]),
            )
            self._write_executor(pack_root, "render", "rendering.render")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            # Old alias lookup
            result = registry.get("builtin.render")
            assert result.id == "rendering.render"

            # Resolver metadata
            assert registry.alias_resolver is not None
            record = registry.alias_resolver.get_record("builtin.render")
            assert record.canonical_id == "rendering.render"
            assert record.deprecated is True
            assert record.deprecation_message == "Moved to rendering.render"
            assert record.source_pack_id == "rendering"

    def test_deprecated_alias_external_vibecomfy_run_resolves_to_vibecomfy_run(self) -> None:
        """``vibecomfy.run`` (deprecated) → ``vibecomfy.run`` (canonical)."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "vibecomfy",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: external.vibecomfy.run",
                    "    canonical_id: vibecomfy.run",
                    "    deprecated: true",
                    "    deprecation_message: Use vibecomfy.run directly",
                ]),
            )
            self._write_executor(pack_root, "run", "vibecomfy.run")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            result = registry.get("external.vibecomfy.run")
            assert result.id == "vibecomfy.run"

            assert registry.alias_resolver is not None
            record = registry.alias_resolver.get_record("external.vibecomfy.run")
            assert record.canonical_id == "vibecomfy.run"
            assert record.deprecated is True
            assert record.deprecation_message == "Use vibecomfy.run directly"
            assert record.source_pack_id == "vibecomfy"

    def test_orchestrator_alias_builtin_hype_resolves_to_video_editing_hype(self) -> None:
        """``video_editing.hype`` (deprecated) → ``video_editing.hype`` (canonical)."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "video_editing",
                aliases="\n".join([
                    "  - kind: orchestrator",
                    "    alias: builtin.hype",
                    "    canonical_id: video_editing.hype",
                    "    deprecated: true",
                    "    deprecation_message: Moved to video_editing.hype",
                ]),
            )
            self._write_orchestrator(pack_root, "hype", "video_editing.hype")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                registry = load_orchestrator_registry()

            result = registry.get("builtin.hype")
            assert result.id == "video_editing.hype"

            assert registry.alias_resolver is not None
            record = registry.alias_resolver.get_record("builtin.hype")
            assert record.canonical_id == "video_editing.hype"
            assert record.deprecated is True

    def test_media_transcribe_alias_to_canonical_executor(self) -> None:
        """``editorial.transcribe`` (non-deprecated alias) → ``media.transcribe``."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "media",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: editorial.transcribe",
                    "    canonical_id: media.transcribe",
                ]),
            )
            self._write_executor(pack_root, "transcribe", "media.transcribe")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            result = registry.get("editorial.transcribe")
            assert result.id == "media.transcribe"

            assert registry.alias_resolver is not None
            record = registry.alias_resolver.get_record("editorial.transcribe")
            assert record.canonical_id == "media.transcribe"
            assert record.deprecated is False

    def test_deprecated_alias_external_runpod_session_resolves_to_runpod_session(self) -> None:
        """``runpod.session`` (deprecated) → ``runpod.session`` (canonical)."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "runpod",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: external.runpod.session",
                    "    canonical_id: runpod.session",
                    "    deprecated: true",
                    "    deprecation_message: Moved to runpod.session",
                ]),
            )
            self._write_executor(pack_root, "session", "runpod.session")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            result = registry.get("external.runpod.session")
            assert result.id == "runpod.session"

            assert registry.alias_resolver is not None
            record = registry.alias_resolver.get_record("external.runpod.session")
            assert record.canonical_id == "runpod.session"
            assert record.deprecated is True
            assert record.deprecation_message == "Moved to runpod.session"
            assert record.source_pack_id == "runpod"

    def test_deprecated_alias_upload_youtube_resolves_to_youtube_upload(self) -> None:
        """``youtube.upload`` (deprecated) → ``youtube.upload`` (canonical)."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "youtube",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: upload.youtube",
                    "    canonical_id: youtube.upload",
                    "    deprecated: true",
                    "    deprecation_message: Moved to youtube.upload",
                ]),
            )
            self._write_executor(pack_root, "upload", "youtube.upload")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            result = registry.get("upload.youtube")
            assert result.id == "youtube.upload"

            assert registry.alias_resolver is not None
            record = registry.alias_resolver.get_record("upload.youtube")
            assert record.canonical_id == "youtube.upload"
            assert record.deprecated is True
            assert record.deprecation_message == "Moved to youtube.upload"
            assert record.source_pack_id == "youtube"

    # -- CLI inspect: JSON output with alias/deprecation metadata ---------

    def test_executor_inspect_json_via_deprecated_alias_returns_canonical_with_metadata(self) -> None:
        """Executing ``executors inspect rendering.render --json`` against a
        temp pack whose pack.yaml declares ``rendering.render → rendering.render``
        should return the canonical definition and carry alias + deprecation
        metadata in the ``_capability`` block."""
        with tempfile.TemporaryDirectory() as tmp:
            import argparse
            import contextlib
            import io
            import json as _json

            from astrid.core.executor.cli import _cmd_inspect

            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "rendering",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: builtin.render",
                    "    canonical_id: rendering.render",
                    "    deprecated: true",
                    "    deprecation_message: Moved to rendering.render",
                ]),
            )
            self._write_executor(pack_root, "render", "rendering.render")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            inspect_stdout = io.StringIO()
            with contextlib.redirect_stdout(inspect_stdout):
                rc = _cmd_inspect(
                    argparse.Namespace(
                        executor_id="builtin.render",
                        json=True,
                        pack=None,
                        show_overrides=False,
                    ),
                    registry,
                )
            assert rc == 0
            payload = _json.loads(inspect_stdout.getvalue())

            # Canonical definition
            assert payload["id"] == "rendering.render"

            # _capability block
            cap = payload["_capability"]
            assert cap["canonical_id"] == "rendering.render"
            assert cap["provenance"]["resolved_alias"] == "builtin.render"
            assert cap["deprecated"] is True
            assert cap["deprecation_message"] == "Moved to rendering.render"
            assert len(cap["aliases"]) >= 1
            alias_ids = [a["alias"] for a in cap["aliases"]]
            assert "builtin.render" in alias_ids

            # Definition metadata must NOT be mutated
            assert "resolved_alias" not in payload.get("metadata", {})
            assert "deprecated" not in payload.get("metadata", {})

    def test_orchestrator_inspect_json_via_deprecated_alias_returns_canonical_with_metadata(self) -> None:
        """Executing ``orchestrators inspect video_editing.hype --json`` against a
        temp pack whose pack.yaml declares ``video_editing.hype → video_editing.hype``
        should return the canonical definition and carry alias + deprecation
        metadata in the ``_capability`` block."""
        with tempfile.TemporaryDirectory() as tmp:
            import argparse
            import contextlib
            import io
            import json as _json

            from astrid.core.orchestrator.cli import _cmd_inspect

            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "video_editing",
                aliases="\n".join([
                    "  - kind: orchestrator",
                    "    alias: builtin.hype",
                    "    canonical_id: video_editing.hype",
                    "    deprecated: true",
                    "    deprecation_message: Moved to video_editing.hype",
                ]),
            )
            self._write_orchestrator(pack_root, "hype", "video_editing.hype")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                registry = load_orchestrator_registry()

            inspect_stdout = io.StringIO()
            with contextlib.redirect_stdout(inspect_stdout):
                rc = _cmd_inspect(
                    argparse.Namespace(
                        orchestrator_id="builtin.hype",
                        json=True,
                        pack=None,
                        show_overrides=False,
                    ),
                    registry,
                )
            assert rc == 0
            payload = _json.loads(inspect_stdout.getvalue())

            # Canonical definition
            assert payload["id"] == "video_editing.hype"

            # _capability block
            cap = payload["_capability"]
            assert cap["canonical_id"] == "video_editing.hype"
            assert cap["provenance"]["resolved_alias"] == "builtin.hype"
            assert cap["deprecated"] is True
            assert cap["deprecation_message"] == "Moved to video_editing.hype"
            assert len(cap["aliases"]) >= 1
            alias_ids = [a["alias"] for a in cap["aliases"]]
            assert "builtin.hype" in alias_ids

            # Definition metadata must NOT be mutated
            assert "resolved_alias" not in payload.get("metadata", {})

    # -- CLI inspect: human-readable output with alias/deprecation --------

    def test_executor_inspect_human_readable_shows_alias_mapping_and_deprecation(self) -> None:
        """Human-readable ``executors inspect`` on a deprecated alias prints
        ``requested_alias`` and ``deprecated`` lines."""
        with tempfile.TemporaryDirectory() as tmp:
            import argparse
            import contextlib
            import io

            from astrid.core.executor.cli import _cmd_inspect

            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "rendering",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: builtin.render",
                    "    canonical_id: rendering.render",
                    "    deprecated: true",
                    "    deprecation_message: Moved to rendering.render",
                ]),
            )
            self._write_executor(pack_root, "render", "rendering.render")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            inspect_stdout = io.StringIO()
            with contextlib.redirect_stdout(inspect_stdout):
                rc = _cmd_inspect(
                    argparse.Namespace(
                        executor_id="builtin.render",
                        json=False,
                        pack=None,
                        show_overrides=False,
                    ),
                    registry,
                )
            assert rc == 0
            output = inspect_stdout.getvalue()

            assert "id: rendering.render" in output
            assert "requested_alias: builtin.render → rendering.render" in output
            assert "deprecated: Moved to rendering.render" in output

    def test_orchestrator_inspect_human_readable_shows_alias_mapping_and_deprecation(self) -> None:
        """Human-readable ``orchestrators inspect`` on a deprecated alias prints
        ``requested_alias`` and ``deprecated`` lines."""
        with tempfile.TemporaryDirectory() as tmp:
            import argparse
            import contextlib
            import io

            from astrid.core.orchestrator.cli import _cmd_inspect

            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "video_editing",
                aliases="\n".join([
                    "  - kind: orchestrator",
                    "    alias: builtin.hype",
                    "    canonical_id: video_editing.hype",
                    "    deprecated: true",
                    "    deprecation_message: Moved to video_editing.hype",
                ]),
            )
            self._write_orchestrator(pack_root, "hype", "video_editing.hype")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                registry = load_orchestrator_registry()

            inspect_stdout = io.StringIO()
            with contextlib.redirect_stdout(inspect_stdout):
                rc = _cmd_inspect(
                    argparse.Namespace(
                        orchestrator_id="builtin.hype",
                        json=False,
                        pack=None,
                        show_overrides=False,
                    ),
                    registry,
                )
            assert rc == 0
            output = inspect_stdout.getvalue()

            assert "id: video_editing.hype" in output
            assert "requested_alias: builtin.hype → video_editing.hype" in output
            assert "deprecated: Moved to video_editing.hype" in output

    # -- Mixed pack: executor + orchestrator aliases in one pack ----------

    def test_mixed_pack_with_both_executor_and_orchestrator_migrated_aliases(self) -> None:
        """A single temp pack declares both executor and orchestrator aliases
        with migration semantics.  Both registries load only their kind-filtered
        aliases and resolve canonical ids correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "migrated",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: builtin.render",
                    "    canonical_id: migrated.render",
                    "    deprecated: true",
                    "  - kind: orchestrator",
                    "    alias: builtin.hype",
                    "    canonical_id: migrated.hype",
                    "    deprecated: true",
                ]),
            )
            self._write_executor(pack_root, "render", "migrated.render")
            self._write_orchestrator(pack_root, "hype", "migrated.hype")
            packs = discover_packs(packs_root)

            # Executor registry
            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                exec_reg = load_executor_registry()
            result = exec_reg.get("builtin.render")
            assert result.id == "migrated.render"
            assert not exec_reg.alias_resolver.is_alias("builtin.hype")

            # Orchestrator registry
            with mock.patch("astrid.core.orchestrator.registry.discover_packs", return_value=packs):
                orch_reg = load_orchestrator_registry()
            result2 = orch_reg.get("builtin.hype")
            assert result2.id == "migrated.hype"
            assert not orch_reg.alias_resolver.is_alias("builtin.render")

    # -- Multiple aliases for one canonical id ----------------------------

    def test_multiple_deprecated_aliases_for_same_canonical(self) -> None:
        """Multiple old ids all resolve to the same canonical id."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = self._write_pack(
                packs_root,
                "rendering",
                aliases="\n".join([
                    "  - kind: executor",
                    "    alias: builtin.render",
                    "    canonical_id: rendering.render",
                    "    deprecated: true",
                    "  - kind: executor",
                    "    alias: old.render",
                    "    canonical_id: rendering.render",
                    "    deprecated: true",
                    "  - kind: executor",
                    "    alias: legacy.render",
                    "    canonical_id: rendering.render",
                ]),
            )
            self._write_executor(pack_root, "render", "rendering.render")
            packs = discover_packs(packs_root)

            with mock.patch("astrid.core.executor.registry.discover_packs", return_value=packs):
                registry = load_executor_registry()

            # All three aliases resolve to the same canonical
            for alias_id in ("builtin.render", "old.render", "legacy.render"):
                result = registry.get(alias_id)
                assert result.id == "rendering.render", f"Alias {alias_id} did not resolve correctly"

            # get_aliases_for lists all three
            assert registry.alias_resolver is not None
            aliases = registry.alias_resolver.get_aliases_for("rendering.render")
            alias_ids = {a.alias for a in aliases}
            assert alias_ids == {"builtin.render", "old.render", "legacy.render"}

    # -- Guard: no real builtin files are touched -------------------------

    def test_no_real_builtin_files_are_moved(self) -> None:
        """Assert that the real source-tree directory for ``builtin`` still exists."""
        repo_root = Path(__file__).resolve().parents[1]
        pack_path = repo_root / "astrid" / "packs" / "builtin"
        assert pack_path.is_dir(), (
            f"Real pack directory {pack_path} is missing; "
            f"temp-pack fixture tests must not move real source-tree files"
        )
        pack_yaml = pack_path / "pack.yaml"
        assert pack_yaml.is_file(), (
            f"pack.yaml missing from {pack_path}; "
            f"temp-pack fixture tests must not alter real pack manifests"
        )
