"""Executor-manifest + execution validation tests for builtin.generate_image.

Covers:
  (a) Manifest validation — executor.yaml passes load_executor_manifest.
  (b) Invalid execution value — rejected with both legal values named.
  (c) Requires violation — i2i without image_ref fails BEFORE HTTP.
  (d) V1 rejection — passing a v1 model-id raises KeyError.
  (e) Edit mode drops negative_prompt with warning (SD-003).
  (f) Edit mode drops strength with warning (SD-003).
  (g) Per-entry model override without mode field rejected (FLAG-004).
  (h) Per-entry model override with mode mismatch rejected (FLAG-004).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.executor.schema import load_executor_manifest
from astrid.core.util.http import Transport


# Path to the executor manifest
_EXECUTOR_YAML = (
    Path(__file__).resolve().parents[4]
    / "astrid/packs/builtin/generate_image/executor.yaml"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _logging_transport_with_upload(request: object) -> tuple[int, bytes]:
    """Transport that logs calls and handles fal-upload + submission + image download."""
    import json

    url = request.full_url if hasattr(request, "full_url") else str(request)
    method = request.method if hasattr(request, "method") else "GET"
    _logging_transport_with_upload.calls.append(url)  # type: ignore[attr-defined]

    # fal-upload endpoint
    if "fal-upload" in str(url):
        return 200, json.dumps({"url": "https://fal.media/files/mock-upload.png"}).encode("utf-8")

    # fal submission POST — return a valid submit response
    if method == "POST" and "fal.run" in str(url):
        return 200, json.dumps({
            "request_id": "mock-req-001",
            "status_url": "https://queue.fal.run/fal-ai/test/requests/mock-req-001/status",
            "response_url": "https://queue.fal.run/fal-ai/test/requests/mock-req-001",
        }).encode("utf-8")

    # Status poll — return COMPLETED
    if "/status" in str(url):
        return 200, json.dumps({"status": "COMPLETED"}).encode("utf-8")

    # Response poll — return result with images
    if "/requests/" in str(url) and "/status" not in str(url):
        return 200, json.dumps({
            "images": [{"url": "https://fal.media/files/mock-result.png"}],
        }).encode("utf-8")

    # Image download — return tiny PNG
    if method == "GET" and "fal.media" in str(url):
        return 200, (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
            b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    return 200, b"{}"


_logging_transport_with_upload.calls = []  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# (a) Manifest validation
# ---------------------------------------------------------------------------


def test_manifest_loads() -> None:
    """load_executor_manifest succeeds on the shipped executor.yaml."""
    manifest = load_executor_manifest(str(_EXECUTOR_YAML))
    assert manifest.id == "builtin.generate_image"
    assert manifest.kind == "built_in"
    assert manifest.version == "2.0"
    # v2 executor has 13 inputs: mode, prompt, prompts_file, model, image_ref,
    # execution, count, seed, negative_prompt, size, strength, guidance_scale, steps
    assert len(manifest.inputs) == 13
    assert len(manifest.outputs) == 2  # generated_images, image_manifest


# ---------------------------------------------------------------------------
# (b) Invalid execution value
# ---------------------------------------------------------------------------


def test_execution_invalid_value(tmp_path: Path) -> None:
    """Invoking run with --execution both exits non-zero with message naming legal values."""
    from astrid.packs.builtin.generate_image.run import main

    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "both",
                "--prompt", "x",
                "--out", str(out),
            ]
        )
    # argparse exits with code 2 for invalid choice
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# (c) Requires violation — hard-fail BEFORE any HTTP call
# ---------------------------------------------------------------------------


def test_requires_violation_no_http(tmp_path: Path) -> None:
    """flux-dev --mode i2i without --image-ref exits non-zero BEFORE any HTTP call.

    We inject a transport that records every call and assert the log is empty.
    """
    from astrid.packs.builtin.generate_image.run import main
    from astrid.core.util.http import default_client

    class CallLog:
        def __init__(self) -> None:
            self.calls: list[object] = []

    log = CallLog()

    def _logging_transport(request: object) -> tuple[int, bytes]:
        url = request.full_url if hasattr(request, "full_url") else ""
        if isinstance(url, str) and "fal-upload" in url:
            return 200, b'{"url": "https://fal.media/files/test-uploaded-image.png"}'
        log.calls.append(request)
        return 200, b"{}"

    # Inject the logging transport into the default (singleton) client *and*
    # also patch default_client to return our instrumented instance.  The
    # executor calls default_client() for cloud execution, so we must ensure
    # that path never fires before the requires check.
    import astrid.core.util.http as http_mod
    original_default = http_mod._default_client
    instrumented = http_mod.HttpClient(transport=_logging_transport)
    http_mod._default_client = instrumented

    try:
        out = tmp_path / "out"
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    "--model", "flux-dev",
                    "--mode", "i2i",
                    "--execution", "cloud",
                    "--prompt", "a test prompt",
                    "--out", str(out),
                ]
            )
        # Should exit non-zero on requires violation (SystemExit carries the
        # error message string as its code — truthy means failure)
        assert exc.value.code, f"Expected non-zero exit, got {exc.value.code!r}"
        # Zero HTTP calls — the requires check happens BEFORE the loop
        assert len(log.calls) == 0, (
            f"Expected zero HTTP calls before requires check, got {len(log.calls)}"
        )
    finally:
        http_mod._default_client = original_default


# ---------------------------------------------------------------------------
# (d) V1 rejection — v1 model-id raises KeyError
# ---------------------------------------------------------------------------


def test_v1_model_id_rejected(tmp_path: Path) -> None:
    """Passing a v1 model-id like 'flux-dev-img2img' raises KeyError.

    In v2, modes are separate from model IDs.  'flux-dev-img2img' is not a
    valid v2 model ID — the correct v2 invocation is 'flux-dev --mode i2i'.
    """
    from astrid.packs.builtin.generate_image.run import main

    out = tmp_path / "out"
    # flux-dev-img2img does not exist in the v2 registry — should fail
    code = main(
        [
            "--model", "flux-dev-img2img",
            "--mode", "t2i",
            "--execution", "cloud",
            "--prompt", "a test",
            "--out", str(out),
        ]
    )
    assert code != 0, "Expected non-zero exit for v1 model-id"


# ---------------------------------------------------------------------------
# (e) Edit mode drops negative_prompt with warning
# ---------------------------------------------------------------------------


def test_edit_mode_rejects_negative_prompt(tmp_path: Path) -> None:
    """qwen-image-edit in edit mode drops --negative-prompt as unsupported (SD-003)."""
    from astrid.packs.builtin.generate_image.run import main

    import astrid.core.util.http as http_mod

    original_default = http_mod._default_client
    instrumented = http_mod.HttpClient(transport=_logging_transport_with_upload)
    http_mod._default_client = instrumented

    try:
        out = tmp_path / "out"
        ref_image = tmp_path / "ref.png"
        ref_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        code = main(
            [
                "--model", "qwen-image-edit",
                "--mode", "edit",
                "--execution", "cloud",
                "--prompt", "replace the background with a forest",
                "--image-ref", str(ref_image),
                "--negative-prompt", "blurry",
                "--out", str(out),
            ]
        )
        assert code == 0

        import json
        manifest_path = out / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "edit"

        # negative_prompt should be dropped with warning
        warning_features = [w["feature"] for w in manifest.get("warnings", [])]
        assert "negative_prompt" in warning_features, (
            f"Expected negative_prompt in warnings, got {warning_features}"
        )
        assert "dropped_features" in manifest
        assert "negative_prompt" in manifest["dropped_features"]
    finally:
        http_mod._default_client = original_default


# ---------------------------------------------------------------------------
# (f) Edit mode drops strength with warning
# ---------------------------------------------------------------------------


def test_edit_mode_rejects_strength(tmp_path: Path) -> None:
    """qwen-image-edit in edit mode drops --strength as unsupported (SD-003)."""
    from astrid.packs.builtin.generate_image.run import main

    import astrid.core.util.http as http_mod

    original_default = http_mod._default_client
    instrumented = http_mod.HttpClient(transport=_logging_transport_with_upload)
    http_mod._default_client = instrumented

    try:
        out = tmp_path / "out"
        ref_image = tmp_path / "ref.png"
        ref_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        code = main(
            [
                "--model", "qwen-image-edit",
                "--mode", "edit",
                "--execution", "cloud",
                "--prompt", "make it brighter",
                "--image-ref", str(ref_image),
                "--strength", "0.7",
                "--out", str(out),
            ]
        )
        assert code == 0

        import json
        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["schema_version"] == 2
        assert manifest["mode_used"] == "edit"

        # strength should be dropped with warning
        warning_features = [w["feature"] for w in manifest.get("warnings", [])]
        assert "strength" in warning_features, (
            f"Expected strength in warnings, got {warning_features}"
        )
        assert "dropped_features" in manifest
        assert "strength" in manifest["dropped_features"]
    finally:
        http_mod._default_client = original_default


# ---------------------------------------------------------------------------
# (g) Per-entry model override without mode field rejected
# ---------------------------------------------------------------------------


def test_per_entry_model_override_without_mode_rejected(tmp_path: Path) -> None:
    """Per-entry model override without 'mode' field is rejected (FLAG-004)."""
    from astrid.packs.builtin.generate_image.run import main

    prompts_file = tmp_path / "prompts.jsonl"
    prompts_file.write_text(
        '{"prompt": "test", "model": "z-image"}\n'
    )

    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompts-file", str(prompts_file),
                "--out", str(out),
            ]
        )
    assert exc.value.code, f"Expected non-zero exit, got {exc.value.code!r}"


# ---------------------------------------------------------------------------
# (h) Per-entry model override with mode mismatch rejected
# ---------------------------------------------------------------------------


def test_per_entry_model_override_mode_mismatch_rejected(tmp_path: Path) -> None:
    """Per-entry model override with mode different from CLI --mode is rejected (FLAG-004)."""
    from astrid.packs.builtin.generate_image.run import main

    prompts_file = tmp_path / "prompts.jsonl"
    prompts_file.write_text(
        '{"prompt": "test", "model": "z-image", "mode": "i2i"}\n'
    )

    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--model", "flux-dev",
                "--mode", "t2i",
                "--execution", "cloud",
                "--prompts-file", str(prompts_file),
                "--out", str(out),
            ]
        )
    assert exc.value.code, f"Expected non-zero exit, got {exc.value.code!r}"
