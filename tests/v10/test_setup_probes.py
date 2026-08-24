"""Batch B8 fixtures: probe registrations per the E7 table (T8.3).

``wgp_runtime`` / ``wgp_weights:<model>`` / ``vibecomfy_runtime`` /
``vc_weights:<template>`` / ``remotion_ready`` — never CUDA presence.
Probes read one place (the setup-journal stamp); completing setup flips
availability with zero code changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import astrid.core.integrations.reigh.capabilities as caps
from astrid.core.integrations.reigh.capabilities import (
    AVAILABILITY_PROBES,
    CapabilityEntry,
    CapabilityUnavailable,
    _setup_stamp_probe,
    check_available,
    resolve_probe,
)
from astrid.core.model_setup.acquire import acquire_artifact

from tests.v10._setup_harness import (
    RangeOrigin,
    manifest_for,
    sha256_hex,
    store_manifest,
)

WEIGHT_ID = "vc_weights:qwen_image_2512"


@pytest.fixture()
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A projects root the stamp probes consult via ASTRID_PROJECTS_ROOT."""
    from astrid.core.foundation.project_paths import PROJECTS_ROOT_ENV

    monkeypatch.setenv(PROJECTS_ROOT_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture()
def runtime_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the runtime half of the closure so stamps are the variable."""
    monkeypatch.setattr(
        caps, "_probe_vibecomfy_runtime", lambda: (True, [])
    )
    monkeypatch.setattr(caps, "_probe_wgp_runtime", lambda: (True, []))


# ---------------------------------------------------------------------------
# Registration + resolution
# ---------------------------------------------------------------------------


def test_e7_probe_table_is_registered() -> None:
    assert set(AVAILABILITY_PROBES) >= {
        "always_available",
        "vibecomfy_runtime",
        "wgp_runtime",
        "remotion_ready",
    }
    assert resolve_probe("wgp_runtime") is AVAILABILITY_PROBES["wgp_runtime"]


def test_parameterized_weight_probes_resolve_from_name(runtime_ok) -> None:
    for name in ("wgp_weights:wan_t2v_14b", "vc_weights:any-template"):
        probe = resolve_probe(name)
        assert callable(probe)
        ok, missing = probe()
        assert ok is False
        # The missing artifact is named exactly, with one setup command.
        assert any(name in entry for entry in missing)
        assert any("doctor setup" in entry for entry in missing)


def test_unknown_probe_names_resolve_to_none() -> None:
    assert resolve_probe("cuda_available") is None
    assert resolve_probe("wgp_weights:") is None
    assert resolve_probe("weights:missing-prefix") is None


def test_remotion_probe_covers_binaries_and_bundle(monkeypatch) -> None:
    import shutil

    real_which = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/" + name
    )
    ok, missing = AVAILABILITY_PROBES["remotion_ready"]()
    # This checkout has the Remotion bundle installed; binaries stubbed in.
    assert ok is True, missing
    del real_which


# ---------------------------------------------------------------------------
# Unavailable advertisement -> 422 typed refusal
# ---------------------------------------------------------------------------


def test_uninstalled_capability_refuses_with_missing_prerequisites(
    root: Path, runtime_ok
) -> None:
    entry = CapabilityEntry(
        capability_id="reigh.qwen_image",
        family="image_generation",
        binding="vibecomfy",
        probe=WEIGHT_ID,
    )
    with pytest.raises(CapabilityUnavailable) as excinfo:
        check_available(entry)
    hint = str(excinfo.value)
    assert "missing_prerequisites" in hint
    assert WEIGHT_ID in hint
    assert "astrid doctor setup" in hint


# ---------------------------------------------------------------------------
# Completing setup flips availability with ZERO code changes
# ---------------------------------------------------------------------------


def test_completing_setup_flips_probe_without_code_changes(
    root: Path, runtime_ok
) -> None:
    probe = resolve_probe(WEIGHT_ID)
    assert probe() == (
        False,
        [
            f"{WEIGHT_ID} not installed (setup stamp absent); "
            "run 'astrid doctor setup'"
        ],
    )

    content = b"weights-bytes" * 1024
    manifest = manifest_for(content, artifact_id=WEIGHT_ID)
    store_manifest(root, manifest)
    with RangeOrigin(payload=content) as origin:
        result = acquire_artifact(manifest, root, origin.url)

    assert result.sha256 == sha256_hex(content)
    # Same process, same code, same registry — only data moved.
    assert probe()[0] is True


def test_stamp_read_is_the_single_probe_read_place(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The weight probe composes ONLY runtime closure + journal stamp."""
    import astrid.core.foundation.project_paths as pp

    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_stamp(projects_root, artifact_ids):
        calls.append((str(projects_root), tuple(artifact_ids)))
        return False, [f"{artifact_ids[0]} not installed"]

    monkeypatch.setattr(
        "astrid.core.model_setup.journal.read_stamp", fake_stamp
    )
    probe = _setup_stamp_probe("wgp_weights:m", lambda: (True, []))
    ok, missing = probe()
    assert ok is False and missing == ["wgp_weights:m not installed"]
