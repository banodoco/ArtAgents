"""B9.1 source reconciliation and no-drop coverage."""

from pathlib import Path

from astrid.core.execution.capability_ledger import load_capability_ledger


def test_shipped_ledger_reconciles_historical_capability_sets():
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    sources = ledger["sources"]

    assert sources["counts"]["pack_labels"] == 83
    assert sources["counts"]["historical_pack_labels"] == 88
    assert sources["counts"]["executor_inventory"] == 74
    assert sources["counts"]["legacy_ids"] == 19
    assert all(section["complete"] for section in sources["coverage"].values())
    assert not sources["coverage"]["source_labels"]["missing"]
    assert sources["coverage"]["historical_source_labels"]["complete"]
    assert not sources["coverage"]["executor_inventory"]["missing"]
    assert not sources["coverage"]["legacy_ids"]["missing"]


def test_ledger_has_only_canonical_ids_models_backends_and_explicit_unmapped_labels():
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    sources = ledger["sources"]

    assert sources["aliases"] == []
    assert sources["models"]
    assert {"local", "cloud"} <= set(sources["generation_backends"])
    assert {row["id"] for row in sources["rendering_backends"]} >= {"rendering.ffmpeg", "rendering.remotion", "rendering.threejs"}
    assert any(row["disposition"] == "unmapped_source_label" for row in sources["pack_labels"])


def test_host_consumes_the_reconciled_ledger_before_readiness_matrix():
    from astrid.core.execution.generic_host import GenericPackHost

    host = GenericPackHost(pack_roots=[Path("astrid/packs")])
    assert host.ledger["sources"]["counts"]["pack_labels"] == 83
    assert len(host.matrix) == 63


def test_historical_external_executor_rows_are_explicitly_not_installed():
    """Historical rows must not be mistaken for executable local routes."""
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    rows = ledger["sources"]["executor_inventory"]
    absent = {row["id"]: row for row in rows if row["discovery_status"] != "discovered"}

    assert set(absent) == {
        "discord_local.command",
        "hivemind.contribute",
        "hivemind.get_item",
        "hivemind.ingest_article",
        "hivemind.ingest_workflow",
        "hivemind.ingest_youtube",
        "hivemind.refresh_media",
        "hivemind.search",
        "seedance_local.reference_video",
        "iteration.prepare",
        "reigh.open_in_reigh",
        "reigh.publish",
        "reigh.reigh_data",
        "reigh.spatial_audio_page",
        "training.asset_cache",
    }
    external = {row["id"]: row for row in absent.values() if row["id"].split(".", 1)[0] in {"discord_local", "hivemind", "seedance_local"}}
    historical = {row["id"]: row for row in absent.values() if row["id"] not in external}
    assert {row["disposition"] for row in external.values()} == {"unavailable_external"}
    assert {row["discovery_status"] for row in external.values()} == {"not_installed"}
    assert {row["disposition"] for row in historical.values()} == {"retired", "unsupported"}
    assert {row["discovery_status"] for row in historical.values()} == {"historical_only"}
    assert all(row["executable"] is False for row in historical.values())


def test_historical_source_labels_preserve_retirements_and_replacement():
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    rows = {f"{row['pack']}.{row['label']}": row for row in ledger["sources"]["historical_pack_labels"]}

    assert rows["iteration.collect_thread_provenance"]["disposition"] == "replaced"
    assert rows["iteration.collect_thread_provenance"]["equivalent_to"] == "iteration.collect_runtime_provenance"
    assert rows["iteration.collect_thread_provenance"]["executable"] is False
    assert rows["reigh.publish_timeline"]["disposition"] == "unsupported"
    assert rows["typed_timeline.typed_timeline.render"]["disposition"] == "retired"


def test_removed_reigh_registry_is_historical_and_inert():
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    rows = ledger["sources"]["legacy_ids"]

    assert len(rows) == 19
    assert {row["id"] for row in rows} == {
        "reigh.wan_2_2_t2i",
        "reigh.qwen_image",
        "reigh.qwen_image_style",
        "reigh.qwen_image_2512",
        "reigh.z_image_turbo",
        "reigh.image_upscale",
        "reigh.individual_travel_segment",
        "reigh.join_clips_orchestrator",
        "reigh.video_enhance",
        "reigh.z_image_turbo_i2i",
        "reigh.qwen_image_edit",
        "reigh.image_inpaint",
        "reigh.annotated_image_edit",
        "reigh.travel_orchestrator",
        "reigh.wan_2_2_i2v",
        "reigh.travel_stitch",
        "reigh.edit_video_orchestrator",
        "reigh.animate_character",
        "reigh.flux_klein_edit",
    }
    assert {row["disposition"] for row in rows} == {"retired"}
    assert {row["discovery_status"] for row in rows} == {"historical_only"}
    assert all(row["executable"] is False for row in rows)


def test_hivemind_census_does_not_guess_the_unresolved_eighth_item():
    ledger = load_capability_ledger(Path("config/astrid-beta-capabilities.json"))
    census = ledger["sources"]["hivemind"]["external_census"]

    assert census == {
        "declared_count": 7,
        "installed_count": 8,
        "unresolved": True,
        "note": "The eighth installed Hivemind item is not identified; no ID is guessed.",
    }
