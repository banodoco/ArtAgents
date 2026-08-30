"""Regression coverage for the Stage 1 core package boundaries.

The graph check is static: it parses imports without importing the product
runtime, so this test cannot accidentally hide a cycle behind environment or
user-specific configuration.
"""

from pathlib import Path

from scripts.reshape.import_cycles import build_graph, cycle_pairs

REPAIRED_PAIRS = {
    frozenset(("events", "repositories")),
    frozenset(("events", "schema_packs")),
    frozenset(("integrations", "kernel")),
    frozenset(("integrations", "project")),
    frozenset(("preferences", "session")),
}


def test_stage1_core_boundaries_remain_acyclic() -> None:
    root = Path(__file__).resolve().parents[2] / "astrid" / "core"
    graph = build_graph(root, "astrid.core", "top", True)
    present = {
        frozenset((left.rsplit(".", 1)[-1], right.rsplit(".", 1)[-1]))
        for left, right in cycle_pairs(graph)
    }
    assert REPAIRED_PAIRS.isdisjoint(present)


def test_event_registry_has_no_trailing_whitespace() -> None:
    registry = (
        Path(__file__).resolve().parents[2]
        / "astrid"
        / "core"
        / "events"
        / "registry.py"
    )
    assert all(
        not line.rstrip("\n").endswith((" ", "\t"))
        for line in registry.read_text().splitlines(True)
    )


def test_schema_pack_core_owns_the_public_core_manifest() -> None:
    from astrid.core.events import registry as event_registry
    from astrid.core.schema_packs import core as schema_core

    assert event_registry.core_schema_pack_manifest is (
        schema_core.core_schema_pack_manifest
    )
    assert event_registry.register_core_vocabulary is (
        schema_core.register_core_vocabulary
    )
    assert event_registry.core_only_registry is schema_core.core_only_registry
    assert "astrid.core.migrations.catalog" not in (
        Path(schema_core.__file__).read_text()
    )
