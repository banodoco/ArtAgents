"""Tests for AliasResolver — alias registration, resolution, cycle detection,
and orchestrator child-executor alias resolution in validation.

All tests construct AliasResolver instances inline.  No real registry loads.
tests/test_canonical_aliases.py is NOT modified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core import AliasResolutionError as AliasResolutionErrorFromCore
from astrid.core import AliasResolver as AliasResolverFromCore
from astrid.core.pack import PackDefinition
from astrid.core.pack.alias_resolver import (
    AliasResolutionError,
    AliasResolver,
    _register_pack_aliases,
    create_shared_alias_resolver,
    extract_pack_aliases,
)

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
        from astrid.core.contracts.schema import AliasRecord

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


# ---------------------------------------------------------------------------
# T10: Search alias visibility — aliases field in search records
# ---------------------------------------------------------------------------


class TestAliasSearchRecords:
    """Search record builders include alias ids in the fields dict so that
    alias terms score against canonical capabilities without duplicate hits."""

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
