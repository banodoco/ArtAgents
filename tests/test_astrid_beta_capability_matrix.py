from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.execution.generic_host import GenericPackHost


def test_beta_matrix_covers_every_discovered_capability_and_declaration():
    host = GenericPackHost(pack_roots=[Path("astrid/packs")])
    records = host.discover()
    assert len(records) == len(host.matrix) == 59
    assert {record.matrix["disposition"] for record in records} <= {"required", "optional", "unsupported", "retired"}
    for record in records:
        assert record.matrix["evidence_reason"]
        assert record.matrix["adapter_family"] == record.adapter.family
        assert isinstance(record.resource_keys, tuple) and record.resource_keys
        assert record.capability_digest and record.source_digest
        assert isinstance(record.manifest()["inputs"], list)
        assert isinstance(record.manifest()["outputs"], list)


def test_beta_reference_family_preflight_is_truthful_on_this_machine():
    host = GenericPackHost(pack_roots=[Path("astrid/packs")])
    host.discover()
    host.preflight()

    cpu = host.capabilities["editorial.arrange"]
    assert cpu.adapter.family == "cpu"
    assert cpu.ready

    provider = host.capabilities["generation.generate_image_openai"]
    assert provider.adapter.family == "provider"
    if not provider.ready:
        assert provider.preflight["credentials"]["missing"]

    render = host.capabilities["rendering.render"]
    assert render.adapter.family == "render"
    assert render.adapter.requires_remotion is True
    assert "remotion" in render.preflight
    if not render.ready:
        assert not render.preflight["remotion"]["ok"] or render.preflight["binaries"]["missing"]

    # These helpers are offline pack executors.  They share the rendering
    # namespace but do not inherit the final compositor's Remotion dependency.
    for capability_id in (
        "rendering.html_canvas_effect",
        "rendering.sprite_sheet",
        "rendering.timeline_storyboard",
        "rendering.timeline_visualize",
    ):
        helper = host.capabilities[capability_id]
        assert helper.adapter.family == "render"
        assert helper.adapter.requires_remotion is False
        assert "remotion" not in helper.preflight
        if capability_id == "rendering.sprite_sheet" and not helper.ready:
            assert helper.preflight["binaries"]["missing"] == ["ffmpeg"]
            pytest.skip(
                "OPTIONAL_FFMPEG: rendering.sprite_sheet requires ffmpeg "
                "on this host"
            )
        assert helper.ready

    local = host.capabilities["vibecomfy.run"]
    assert local.adapter.family == "local_generation"
    if not local.ready:
        assert local.preflight["packages"]["missing"]


def test_provider_ledger_rows_are_networked_and_credential_dispositions_match():
    """B9.4: provider declarations cannot silently become offline executors."""
    host = GenericPackHost(pack_roots=[Path("astrid/packs")])
    records = host.discover()
    provider_rows = [record for record in records if record.adapter.family == "provider"]
    assert provider_rows

    by_credential = {
        str(row["credential"]): set(row["capabilities"])
        for row in host.ledger["sources"]["providers"]
    }
    for record in provider_rows:
        assert record.definition.isolation.network is True
        required_env = record.matrix.get("required_env") or ()
        for credential in required_env:
            assert record.id in by_credential[str(credential)]
        # A source manifest's provider metadata and the frozen matrix must
        # agree on the family; this catches a provider accidentally advertised
        # as a CPU/local capability after a manifest edit.
        assert record.matrix["adapter_family"] == "provider"


def test_manifest_secrets_reconcile_to_provider_readiness(monkeypatch):
    for key in ("GIPHY_API_KEY", "FAL_KEY"):
        monkeypatch.delenv(key, raising=False)
    host = GenericPackHost(pack_roots=[Path("astrid/packs")])
    host.discover()
    host.preflight()
    assert host.capabilities["media.gif_search"].preflight["credentials"]["missing"] == ["GIPHY_API_KEY"]
    assert host.capabilities["media.gif_search"].ready is False
    for capability_id in ("media.speech_repair_lavasr", "fal.h3_video"):
        record = host.capabilities[capability_id]
        assert record.preflight["credentials"]["missing"] == ["FAL_KEY"]
        assert record.ready is False
