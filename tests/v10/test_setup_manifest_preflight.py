"""Batch B8 fixtures: signed versioned manifests, tier discovery,
disk preflight (T8.2).

Signature trust is fail-closed; tier discovery never derives from CUDA
presence; preflight refusal names the exact shortfall.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from astrid.core.model_setup.manifest import (
    Environment,
    ManifestError,
    canonical_bytes,
    load_manifest,
    parse_manifest,
    save_manifest,
    select_bundle,
    verify_signature,
)
from astrid.core.model_setup.preflight import (
    DEFAULT_OUTPUT_HEADROOM_BYTES,
    DiskPreflightError,
    preflight_disk,
    require_disk,
    required_bytes,
)
from tests.v10._setup_harness import manifest_for, sha256_hex, store_manifest

CONTENT = b"distribution-bytes" * 1024


# ---------------------------------------------------------------------------
# Signed versioned manifest
# ---------------------------------------------------------------------------


def test_manifest_roundtrip_preserves_signed_payload(tmp_path) -> None:
    manifest = manifest_for(CONTENT)
    assert verify_signature(manifest)
    path = tmp_path / "m.json"
    save_manifest(manifest, path)
    loaded = load_manifest(path)
    assert loaded.artifact_id == manifest.artifact_id
    assert loaded.sha256 == sha256_hex(CONTENT)
    assert loaded.size == len(CONTENT)


def test_tampered_manifest_payload_fails_signature_closed(tmp_path) -> None:
    manifest = manifest_for(CONTENT)
    payload = manifest.to_dict()
    payload["sha256"] = sha256_hex(b"attacker bytes")
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ManifestError, match="signature mismatch"):
        load_manifest(path)


def test_unknown_schema_version_fails_closed(tmp_path) -> None:
    manifest = manifest_for(CONTENT)
    payload = manifest.to_dict()
    payload["schema"] = "astrid.distribution_manifest.v999"
    path = tmp_path / "future.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ManifestError, match="schema"):
        load_manifest(path)


def test_license_identity_and_text_hash_are_signed_parts() -> None:
    license_text = b"Copyright 2026 Astrid contributors"
    manifest = manifest_for(
        CONTENT, license_identity="Apache-2.0", license_text=license_text
    )
    assert manifest.license_identity == "Apache-2.0"
    assert manifest.license_text_sha256 == sha256_hex(license_text)
    # The signature covers the license fields: swapping identity breaks it.
    forged = dataclasses.replace(manifest, license_identity="GPL-3.0")
    assert not verify_signature(forged)
    # Canonical encoding is stable: same payload -> same signature bytes.
    assert canonical_bytes(manifest.unsigned_payload()) == canonical_bytes(
        parse_manifest(manifest.to_dict()).unsigned_payload()
    )


# ---------------------------------------------------------------------------
# Tier discovery (never CUDA-presence probing)
# ---------------------------------------------------------------------------


def _env(**overrides) -> Environment:
    defaults = dict(
        os="linux", arch="x86_64", ram_bytes=8 << 30, disk_free_bytes=1 << 40
    )
    defaults.update(overrides)
    return Environment(**defaults)


def test_select_bundle_prefers_highest_compatible_version() -> None:
    old = manifest_for(CONTENT, artifact_id="a_old", version="1.0.0")
    new = manifest_for(CONTENT, artifact_id="b_new", version="2.0.0")
    assert select_bundle([old, new], _env()) is new


def test_gpu_tier_bundle_refused_on_cpu_environment() -> None:
    cpu_only = manifest_for(CONTENT, artifact_id="cpu_bundle", tier="cpu")
    gpu_only = manifest_for(CONTENT, artifact_id="gpu_bundle", tier="gpu")
    env = _env(tier="cpu")
    # The sanctioned CPU tier is always satisfiable; gpu is never assumed
    # from hardware probing — Environment.tier is declared, default cpu.
    assert select_bundle([cpu_only, gpu_only], env) is cpu_only


def test_gpu_tier_bundle_selected_on_gpu_environment() -> None:
    gpu_only = manifest_for(CONTENT, artifact_id="gpu_bundle", tier="gpu")
    assert select_bundle([gpu_only], _env(tier="gpu")) is gpu_only


def test_os_arch_mismatch_refuses_with_typed_error() -> None:
    foreign = manifest_for(
        CONTENT,
        artifact_id="foreign",
        os_list=("windows",),
        arch_list=("arm64",),
    )
    with pytest.raises(ManifestError, match="compatible"):
        select_bundle([foreign], _env())


def test_ram_floor_filters_incompatible_bundles() -> None:
    heavy = manifest_for(CONTENT, artifact_id="heavy", min_ram_bytes=64 << 30)
    light = manifest_for(CONTENT, artifact_id="light", min_ram_bytes=0)
    assert select_bundle([heavy, light], _env(ram_bytes=8 << 30)) is light


# ---------------------------------------------------------------------------
# Disk preflight: download + working + output headroom
# ---------------------------------------------------------------------------

def test_required_bytes_sums_download_working_and_output() -> None:
    assert required_bytes(download_bytes=1000) == (
        1000 * 2 + DEFAULT_OUTPUT_HEADROOM_BYTES
    )


def test_preflight_reports_shortfall_and_require_disk_raises(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import astrid.core.model_setup.preflight as preflight

    class _Tiny:
        total = 1 << 20
        used = 0
        free = 1024

    monkeypatch.setattr(preflight.shutil, "disk_usage", lambda _p: _Tiny())
    result = preflight_disk(tmp_path, download_bytes=1 << 30)
    assert result.ok is False
    assert result.missing_bytes > 0
    with pytest.raises(DiskPreflightError, match="short by"):
        require_disk(tmp_path, download_bytes=1 << 30)


def test_preflight_passes_with_headroom(tmp_path) -> None:
    result = preflight_disk(tmp_path, download_bytes=len(CONTENT))
    assert result.ok is True
    assert result.missing_bytes == 0


def test_store_manifest_roundtrip_through_setup_store(tmp_path) -> None:
    manifest = manifest_for(CONTENT)
    store_manifest(tmp_path, manifest)
    reloaded = load_manifest(
        tmp_path / ".astrid" / "setup" / "manifests" / "test_bundle.json"
    )
    assert reloaded.sha256 == manifest.sha256

