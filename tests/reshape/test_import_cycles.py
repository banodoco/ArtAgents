"""Regression coverage for the Stage 1 core package boundaries.

The graph check is static: it parses imports without importing the product
runtime, so this test cannot accidentally hide a cycle behind environment or
user-specific configuration.
"""

from pathlib import Path

from scripts.reshape.import_cycles import build_graph, cycle_pairs

REPAIRED_PAIRS = {
    frozenset(("events", "schema_packs")),
    frozenset(("integrations", "kernel")),
    frozenset(("integrations", "project")),
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
