"""B9.1 source reconciliation and no-drop coverage."""

from pathlib import Path

from astrid.core.execution.capability_ledger import load_capability_ledger


def test_shipped_ledger_reconciles_historical_capability_sets():
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    sources = ledger["sources"]

    assert sources["counts"]["pack_labels"] == 83
    assert sources["counts"]["historical_pack_labels"] == 81
    assert sources["counts"]["executor_inventory"] == 74
    assert sources["counts"]["legacy_ids"] == 19
    assert all(section["complete"] for section in sources["coverage"].values())
    assert not sources["coverage"]["source_labels"]["missing"]
    assert sources["coverage"]["historical_source_labels"]["complete"]
    assert not sources["coverage"]["executor_inventory"]["missing"]
    assert not sources["coverage"]["legacy_ids"]["missing"]


def test_ledger_preserves_aliases_models_backends_and_explicit_unmapped_labels():
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    sources = ledger["sources"]

    assert sources["aliases"]
    assert {row["canonical_id"] for row in sources["aliases"]} >= {"rendering.render", "generation.generate_image"}
    assert sources["models"]
    assert {"local", "cloud"} <= set(sources["generation_backends"])
    assert {row["id"] for row in sources["rendering_backends"]} >= {"rendering.ffmpeg", "rendering.remotion", "rendering.threejs"}
    assert any(row["disposition"] == "unmapped_source_label" for row in sources["pack_labels"])


def test_host_consumes_the_reconciled_ledger_before_readiness_matrix():
    from astrid.core.execution.generic_host import GenericPackHost

    host = GenericPackHost(pack_roots=[Path("astrid/packs")])
    assert host.ledger["sources"]["counts"]["pack_labels"] == 83
    assert len(host.matrix) == 65
