"""End-to-end tests for builtin.generate_image with recorded fixtures (v2).

Uses canned fal JSON responses and an injected transport so CI runs
end-to-end without burning fal credits.

v2: model -> mode -> backend taxonomy.  --mode is required (SD-005).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request

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
# Fixture-based transport builder
# ---------------------------------------------------------------------------


def _load_fixture(model: str, name: str) -> bytes:
    """Read a canned JSON fixture for *model* and return it as bytes."""
    path = FAL_FIXTURES / model / f"{name}.json"
    return path.read_bytes()


def _build_fal_transport(
    model: str,
    *,
    image_bytes: bytes | None = None,
):
    """Build a transport that routes fal requests to canned fixtures.

    The sequence is:
      1. POST to submit URL  ->  submit.json
      2. GET  to status_url  ->  status.json
      3. GET  to response_url -> response.json
      4. GET  to image URL   ->  raw PNG bytes
    """

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

    def _transport(request: Request) -> tuple[int, bytes]:
        url = request.full_url
        method = request.method
        state.call_log.append(f"{method} {url}")

        # fal-upload endpoint: return a canned upload URL
        if "fal-upload" in url:
            return 200, json.dumps({"url": "https://fal.media/files/test-uploaded-image.png"}).encode("utf-8")

        # Step 1: POST submit
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

        # Step 2: GET status (poll)
        if state.status_url and url == state.status_url:
            return 200, json.dumps(status_data).encode("utf-8")

        # Step 3: GET result (after poll completes)
        if state.response_url and url == state.response_url:
            return 200, json.dumps(response_data).encode("utf-8")

        # Step 4: GET image bytes
        if method == "GET":
            return 200, image_bytes

        # Fallback
        return 200, b"{}"

    state._transport = _transport
    state._transport.call_log = state.call_log
    return state


# ---------------------------------------------------------------------------
# Helper: patch default_client to use our instrumented transport
# ---------------------------------------------------------------------------


def _patch_default_client(transport):
    """Replace the module-level default_client singleton with an instrumented one."""
    import astrid.core.util.http as http_mod

    client = HttpClient(transport=transport)
    http_mod._default_client = client
    return client


def _restore_default_client() -> None:
    """Restore the default_client singleton to a fresh real client."""
    import astrid.core.util.http as http_mod

    http_mod._default_client = None


# ---------------------------------------------------------------------------
# (a) execution=cloud + flux-dev + t2i -> expected v2 manifest
# ---------------------------------------------------------------------------


def test_e2e_cloud_flux_dev_t2i(tmp_path: Path) -> None:
    """Cloud execution with flux-dev t2i mode produces v2 manifest."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompt", "a serene mountain lake at dawn",
                "--out", str(out),
                "--seed", "42",
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())

        # v2 fields
        assert manifest["schema_version"] == 2
        assert manifest["modality"] == "image"
        assert manifest["model"] == "flux-dev"
        assert manifest["mode_used"] == "t2i"
        assert "model_actual" in manifest
        assert manifest["execution"] == "cloud"
        assert manifest["request"]["prompt"] == "a serene mountain lake at dawn"
        assert manifest["seed"] == 42

        assert len(manifest["outputs"]) == 1
        output = manifest["outputs"][0]
        assert output["content_hash"].startswith("sha256:")
        assert output["bytes"] > 0
        assert "images/" in output["path"]

        assert manifest["warnings"] == []

        img_path = out / output["path"]
        assert img_path.exists()
        assert img_path.stat().st_size > 0

        assert len(transport.call_log) >= 3
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (b) execution=cloud + z-image + t2i + negative_prompt -> v2 manifest
# ---------------------------------------------------------------------------


def test_e2e_cloud_z_image_t2i_negative_prompt(tmp_path: Path) -> None:
    """z-image cloud t2i with negative_prompt includes it in request."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "z-image",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompt", "cyberpunk city at night",
                "--negative-prompt", "blurry, low quality",
                "--seed", "100",
                "--out", str(out),
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "t2i"
        assert manifest["model"] == "z-image"
        assert manifest["request"]["prompt"] == "cyberpunk city at night"
        assert manifest["request"]["negative_prompt"] == "blurry, low quality"
        assert manifest["seed"] == 100
        assert manifest["warnings"] == []

        assert len(manifest["outputs"]) == 1
        assert manifest["outputs"][0]["content_hash"].startswith("sha256:")
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (c) execution=cloud + flux-dev + i2i -> v2 manifest with image_ref
# ---------------------------------------------------------------------------


def test_e2e_cloud_flux_dev_i2i(tmp_path: Path) -> None:
    """Cloud execution with flux-dev i2i mode with --image-ref produces correct manifest."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    transport = state._transport
    _patch_default_client(transport)

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
        manifest = json.loads(manifest_path.read_text())

        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "i2i"
        assert manifest["model"] == "flux-dev"
        assert "model_actual" in manifest
        assert manifest["execution"] == "cloud"

        assert manifest["request"]["image_ref_resolved"] is not None
        assert "input.png" in manifest["request"]["image_ref_resolved"]

        assert len(manifest["outputs"]) == 1
        ch = manifest["outputs"][0]["content_hash"]
        assert ch.startswith("sha256:"), f"content_hash={ch!r} not sha256: prefixed"
        assert manifest["outputs"][0]["bytes"] > 0
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (d) execution=cloud + flux-schnell + t2i -> v2 manifest
# ---------------------------------------------------------------------------


def test_e2e_cloud_flux_schnell_t2i(tmp_path: Path) -> None:
    """Cloud execution with flux-schnell t2i mode produces v2 manifest."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("flux-schnell")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "flux-schnell",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompt", "fast generation test",
                "--out", str(out),
                "--seed", "1",
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "t2i"
        assert manifest["model"] == "flux-schnell"
        assert "model_actual" in manifest
        assert manifest["execution"] == "cloud"
        assert len(manifest["outputs"]) == 1
        assert manifest["outputs"][0]["content_hash"].startswith("sha256:")
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (e) i2i mode without image_ref -> hard-fails BEFORE any HTTP
# ---------------------------------------------------------------------------


def test_e2e_i2i_without_image_ref_fails_before_http(tmp_path: Path) -> None:
    """flux-dev i2i mode without --image-ref hard-fails before any HTTP call."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    "--model", "flux-dev",
                    "--mode", "i2i",
                    "--execution", "cloud",
                    "--prompt", "turn this into a watercolor",
                    "--out", str(out),
                ]
            )
        assert exc.value.code, f"Expected non-zero exit, got {exc.value.code!r}"

        assert len(transport.call_log) == 0, (
            f"Expected zero HTTP calls, got: {transport.call_log}"
        )
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (f) flux-dev t2i + image_ref (unsupported) -> completes, warning in manifest
# ---------------------------------------------------------------------------


def test_e2e_flux_dev_t2i_unsupported_image_ref_warns(tmp_path: Path) -> None:
    """Passing image_ref to flux-dev t2i (unsupported) completes with warning (SD-004)."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompt", "a test image",
                "--image-ref", str(INPUT_PNG.absolute()),
                "--out", str(out),
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "t2i"

        assert len(manifest["warnings"]) >= 1
        warning_features = [w["feature"] for w in manifest["warnings"]]
        assert "image_ref" in warning_features

        assert "dropped_features" in manifest
        assert "image_ref" in manifest["dropped_features"]

        assert len(manifest["outputs"]) == 1
        assert manifest["outputs"][0]["content_hash"].startswith("sha256:")
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (g) Lazy-import probe: vibecomfy NOT in sys.modules after cloud run
# ---------------------------------------------------------------------------


def test_e2e_cloud_never_imports_vibecomfy(tmp_path: Path) -> None:
    """Running execution=cloud must NOT import vibecomfy."""
    if "vibecomfy" in sys.modules:
        pytest.skip("vibecomfy already imported -- cannot test lazy-import")

    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("flux-dev")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompt", "lazy import probe",
                "--out", str(out),
            ]
        )
        assert code == 0

        assert "vibecomfy" not in sys.modules, (
            "vibecomfy was imported during cloud execution -- lazy-import violation"
        )
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (h) Local-path positive: execution=local smoke run
# ---------------------------------------------------------------------------


def _vibecomfy_importable() -> bool:
    """Check whether vibecomfy is importable."""
    try:
        import vibecomfy  # noqa: F401
        return True
    except ImportError:
        return False


def _comfyui_binary_present() -> bool:
    import shutil
    return shutil.which("comfyui") is not None


@pytest.mark.skipif(not _vibecomfy_importable(), reason="vibecomfy not importable")
@pytest.mark.skipif(not _comfyui_binary_present(), reason="comfyui binary not on PATH")
def test_e2e_local_smoke(tmp_path: Path) -> None:
    """Smoke test: execution=local with z-image t2i mode runs without crashing."""
    from astrid.packs.builtin.generate_image.run import main

    out = tmp_path / "out"
    code = main(
        [
            "--model", "z-image",
            "--mode", "t2i",
            "--execution", "local",
            "--prompt", "a tiny red triangle",
            "--out", str(out),
            "--seed", "1",
        ]
    )
    assert code in (0, 1)


# ---------------------------------------------------------------------------
# (i) Edit mode drops negative_prompt with warning (SD-003)
# ---------------------------------------------------------------------------


def test_e2e_edit_mode_rejects_negative_prompt(tmp_path: Path) -> None:
    """qwen-image-edit edit mode drops --negative-prompt with warning (SD-003)."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("qwen-image-edit")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "qwen-image-edit",
                "--mode", "edit",
                "--execution", "cloud",
                "--prompt", "replace the background with a forest",
                "--image-ref", str(INPUT_PNG.absolute()),
                "--negative-prompt", "blurry, low quality",
                "--out", str(out),
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "edit"
        assert manifest["model"] == "qwen-image-edit"

        warning_features = [w["feature"] for w in manifest.get("warnings", [])]
        assert "negative_prompt" in warning_features
        assert "negative_prompt" in manifest.get("dropped_features", [])

        assert len(manifest["outputs"]) == 1
    finally:
        _restore_default_client()


# ---------------------------------------------------------------------------
# (j) Edit mode drops strength with warning (SD-003)
# ---------------------------------------------------------------------------


def test_e2e_edit_mode_rejects_strength(tmp_path: Path) -> None:
    """qwen-image-edit edit mode drops --strength with warning (SD-003)."""
    from astrid.packs.builtin.generate_image.run import main

    state = _build_fal_transport("qwen-image-edit")
    transport = state._transport
    _patch_default_client(transport)

    try:
        out = tmp_path / "out"
        code = main(
            [
                "--model", "qwen-image-edit",
                "--mode", "edit",
                "--execution", "cloud",
                "--prompt", "make it brighter",
                "--image-ref", str(INPUT_PNG.absolute()),
                "--strength", "0.7",
                "--out", str(out),
            ]
        )
        assert code == 0

        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "edit"

        warning_features = [w["feature"] for w in manifest.get("warnings", [])]
        assert "strength" in warning_features
        assert "strength" in manifest.get("dropped_features", [])

        assert len(manifest["outputs"]) == 1
    finally:
        _restore_default_client()
