from __future__ import annotations

from pathlib import Path

from astrid.core.execution.generic_host import GenericPackHost


def test_beta_matrix_covers_every_discovered_capability_and_declaration():
    host = GenericPackHost(pack_roots=[Path("astrid/packs")])
    records = host.discover()
    assert len(records) == len(host.matrix) == 65
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
    assert "remotion" in render.preflight
    if not render.ready:
        assert not render.preflight["remotion"]["ok"] or render.preflight["binaries"]["missing"]

    local = host.capabilities["vibecomfy.run"]
    assert local.adapter.family == "local_generation"
    if not local.ready:
        assert local.preflight["packages"]["missing"]
