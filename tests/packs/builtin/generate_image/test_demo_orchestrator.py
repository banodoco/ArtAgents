"""Pytest variant of demo_flux_local_cloud with mocked HTTP transport.

CI-safe — no real fal credits, no vibecomfy required.

v2: model → mode → backend taxonomy.  --mode is required (SD-005).
flux-dev-img2img replaced by flux-dev --mode i2i.
flux-dev is cloud-only (SD-001).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from astrid.core.util.http import HttpClient

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAL_FIXTURES = FIXTURES / "fal"
TINY_PNG = FIXTURES / "tiny.png"
INPUT_PNG = FIXTURES / "input.png"


# ---------------------------------------------------------------------------
# Transport builder (mirrors test_e2e.py pattern)
# ---------------------------------------------------------------------------


def _load_fixture(model: str, name: str) -> bytes:
    """Read a canned JSON fixture for *model*."""
    path = FAL_FIXTURES / model / f"{name}.json"
    return path.read_bytes()


def _build_fal_transport(model: str, image_bytes: bytes | None = None):
    """Build a transport that routes fal requests to canned fixtures."""
    if image_bytes is None:
        image_bytes = TINY_PNG.read_bytes()

    submit_data = json.loads(_load_fixture(model, "submit"))
    status_data = json.loads(_load_fixture(model, "status"))
    response_data = json.loads(_load_fixture(model, "response"))

    class _State:
        pass

    state = _State()
    state.call_log: list[str] = []
    state.status_url: str | None = None
    state.response_url: str | None = None

    def _transport(request):
        url = request.full_url
        method = request.method
        state.call_log.append(f"{method} {url}")

        # fal-upload endpoint: return a canned upload URL
        if "fal-upload" in url:
            return 200, json.dumps({"url": "https://fal.media/files/test-uploaded-image.png"}).encode("utf-8")

        # POST submit
        if method == "POST" and "/requests/" not in url:
            body = json.dumps(submit_data).encode("utf-8")
            st = submit_data.get("status_url")
            rs = submit_data.get("response_url")
            if st and rs:
                state.status_url = st
                state.response_url = rs
            else:
                endpoint = model.replace("fal-ai/", "")
                req_id = submit_data.get("request_id", "test-req-id")
                state.status_url = (
                    f"https://queue.fal.run/fal-ai/{endpoint}/requests/{req_id}/status"
                )
                state.response_url = (
                    f"https://queue.fal.run/fal-ai/{endpoint}/requests/{req_id}"
                )
            return 200, body

        # GET status (poll)
        if state.status_url and url == state.status_url:
            return 200, json.dumps(status_data).encode("utf-8")

        # GET result
        if state.response_url and url == state.response_url:
            return 200, json.dumps(response_data).encode("utf-8")

        # GET image bytes
        if method == "GET":
            return 200, image_bytes

        return 200, b"{}"

    state._transport = _transport
    return state


def _patch_default_client(transport):
    """Replace the module-level default_client singleton."""
    import astrid.core.util.http as http_mod

    client = HttpClient(transport=transport)
    http_mod._default_client = client
    return client


def _restore_default_client():
    """Restore the default_client singleton."""
    import astrid.core.util.http as http_mod

    http_mod._default_client = None


# ---------------------------------------------------------------------------
# (a) flux-dev t2i cloud → manifest shape correct, content_hash populated
# ---------------------------------------------------------------------------


def test_demo_flux_dev_cloud_manifest_shape(tmp_path: Path) -> None:
    """flux-dev --mode t2i cloud execution produces a manifest with all required v2 fields."""
    from astrid.packs.generation.executors.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    _patch_default_client(state._transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompt", "a red triangle on white background",
                "--seed", "42",
                "--out", str(out),
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())

        # Top-level required fields (v2)
        assert manifest["schema_version"] == 2
        assert manifest["modality"] == "image"
        assert manifest["model"] == "flux-dev"
        assert manifest["mode_used"] == "t2i"
        assert manifest["execution"] == "cloud"
        assert "model_actual" in manifest
        assert "request" in manifest
        assert "outputs" in manifest
        assert "seed" in manifest
        assert "created" in manifest
        assert "warnings" in manifest

        # Request echo
        assert manifest["request"]["prompt"] == "a red triangle on white background"
        assert manifest["seed"] == 42

        # Outputs
        assert len(manifest["outputs"]) == 1
        out0 = manifest["outputs"][0]
        assert out0["content_hash"].startswith("sha256:")
        assert out0["bytes"] > 0
        assert "images/" in out0["path"]

        # No warnings
        assert manifest["warnings"] == []
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (b) flux-dev i2i cloud → image_ref honored, content_hash populated
# ---------------------------------------------------------------------------


def test_demo_flux_dev_i2i_cloud_manifest_shape(tmp_path: Path) -> None:
    """flux-dev --mode i2i cloud execution with image_ref produces correct manifest."""
    from astrid.packs.generation.executors.generate_image.run import main

    state = _build_fal_transport("flux-dev-img2img")
    _patch_default_client(state._transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "flux-dev",
                "--mode", "i2i",
                "--execution", "cloud",
                "--prompt", "watercolor style",
                "--image-ref", str(INPUT_PNG.absolute()),
                "--seed", "42",
                "--out", str(out),
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())

        # Top-level (v2)
        assert manifest["schema_version"] == 2
        assert manifest["modality"] == "image"
        assert manifest["model"] == "flux-dev"
        assert manifest["mode_used"] == "i2i"
        assert manifest["execution"] == "cloud"
        assert "model_actual" in manifest

        # Outputs populated
        assert len(manifest["outputs"]) == 1
        ch = manifest["outputs"][0]["content_hash"]
        assert ch.startswith("sha256:"), f"content_hash={ch!r} not sha256: prefixed"
        assert manifest["outputs"][0]["bytes"] > 0

        # image_ref resolved
        assert manifest["request"]["image_ref_resolved"] is not None
        assert "input.png" in manifest["request"]["image_ref_resolved"]
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (c) Cross-mode manifest shape comparison (same model, different modes)
# ---------------------------------------------------------------------------


def test_demo_manifest_shapes_match_across_modes(tmp_path: Path) -> None:
    """flux-dev t2i and i2i cloud manifests have matching top-level key sets.

    In v2, modes are part of the same model, not separate model IDs.
    """
    from astrid.packs.generation.executors.generate_image.run import main

    manifests: dict[str, dict] = {}

    scenarios = [
        ("t2i", "flux-dev", [
            "--model", "flux-dev",
            "--mode", "t2i",
            "--execution", "cloud",
            "--prompt", "test",
            "--seed", "1",
        ]),
        ("i2i", "flux-dev-img2img", [
            "--model", "flux-dev",
            "--mode", "i2i",
            "--execution", "cloud",
            "--prompt", "test",
            "--seed", "1",
            "--image-ref", str(INPUT_PNG.absolute()),
        ]),
    ]

    for label, fixture_model, argv in scenarios:
        state = _build_fal_transport(fixture_model)
        _patch_default_client(state._transport)
        try:
            out = tmp_path / f"out_{label}"
            argv_full = argv + ["--out", str(out)]
            code = main(argv_full)
            assert code == 0
            manifests[label] = json.loads((out / "manifest.json").read_text())
        finally:
            _restore_default_client()

    # Compare top-level key sets
    keys_t2i = set(manifests["t2i"].keys())
    keys_i2i = set(manifests["i2i"].keys())

    # Common required keys (v2 adds mode_used, model_actual)
    common = {"schema_version", "modality", "model", "mode_used",
              "model_actual", "execution", "request", "outputs",
              "seed", "created", "warnings"}
    assert common <= keys_t2i, f"t2i missing: {common - keys_t2i}"
    assert common <= keys_i2i, f"i2i missing: {common - keys_i2i}"

    # Schema version match (v2)
    assert manifests["t2i"]["schema_version"] == manifests["i2i"]["schema_version"] == 2
    assert manifests["t2i"]["modality"] == manifests["i2i"]["modality"] == "image"

    # Mode used differs
    assert manifests["t2i"]["mode_used"] == "t2i"
    assert manifests["i2i"]["mode_used"] == "i2i"

    # Same model ID
    assert manifests["t2i"]["model"] == manifests["i2i"]["model"] == "flux-dev"

    # Both have content_hash
    for label, m in manifests.items():
        assert m["outputs"][0]["content_hash"].startswith("sha256:"), \
            f"{label} content_hash missing"


# ---------------------------------------------------------------------------
# (d) Lazy-import probe for demo paths
# ---------------------------------------------------------------------------


def test_demo_cloud_never_imports_vibecomfy(tmp_path: Path) -> None:
    """Demo cloud execution path must NOT import vibecomfy."""
    if "vibecomfy" in sys.modules:
        pytest.skip("vibecomfy already imported — cannot test lazy-import")

    from astrid.packs.generation.executors.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    _patch_default_client(state._transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompt", "test lazy import",
                "--out", str(out),
            ]
        )
        assert code == 0
        assert "vibecomfy" not in sys.modules, \
            "vibecomfy was imported during cloud execution"
    finally:
        _restore_default_client()
