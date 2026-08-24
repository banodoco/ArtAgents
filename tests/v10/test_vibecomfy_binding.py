"""Generic VibeComfy binding tests (Batch B2 / T2.1).

Named evidence for the first real-subprocess binding:

- **Digest fence before spawn** — tampered vendored bytes refuse with the
  typed mismatch error and the subprocess is never spawned.
- **Missing checkout** — an absent pinned checkout refuses typed, closed.
- **Malformed workflow** — unparseable/non-graph workflow refuses typed.
- **Typed-port injection** — t2i / i2i / edit shapes each inject
  prompt/image/mask/seed/size through the shared node-target logic.
- **CPU smoke determinism** — the weightless EmptyImage→SaveImage journey
  workflow runs three times through the real subprocess with a stable
  decoded-pixel SHA-256 (~13 s warm per invocation).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from astrid.core.integrations.reigh import vibecomfy_binding as binding
from astrid.core.integrations.reigh.vibecomfy_binding import (
    MalformedWorkflow,
    PortInjectionError,
    RuntimeUnavailable,
    VibeComfyTaskHandler,
    WorkflowDigestMismatch,
    inject_ports,
    resolve_runtime,
)
from astrid.core.task_executor.service import resolve_task_handler

SMOKE_WORKFLOW = {
    "1": {
        "class_type": "EmptyImage",
        "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 16711680},
    },
    "2": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "b2_smoke_red", "images": ["1", 0]},
    },
}


def _task(spec: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(spec=spec, capability=spec.get("source_task_type", ""))


def _local_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    workflow: Any,
    params: dict | None = None,
) -> dict[str, Any]:
    """Admit a declared local workflow: bytes + YAML row + env wiring."""
    wf_path = tmp_path / "wf.json"
    if isinstance(workflow, str):
        wf_path.write_text(workflow, encoding="utf-8")
    else:
        wf_path.write_text(json.dumps(workflow), encoding="utf-8")
    digest = hashlib.sha256(wf_path.read_bytes()).hexdigest()
    declarations = tmp_path / "workflows"
    declarations.mkdir(exist_ok=True)
    (declarations / "smoke_red.yaml").write_text(
        f"id: smoke_red\nworkflow_path: {wf_path}\ndigest: {digest}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ASTRID_LOCAL_WORKFLOWS", str(declarations))
    return {
        "source_task_type": "local.smoke_red",
        "params": params or {},
        "workflow": {
            "path": str(wf_path),
            "sha256": digest,
            "workflow": workflow,
        },
    }


def _runtime_or_skip():
    try:
        return resolve_runtime()
    except RuntimeUnavailable as exc:  # pragma: no cover - environment
        pytest.skip(f"pinned VibeComfy runtime not provisioned: {exc}")


# ---------------------------------------------------------------------------
# Registration (one authority per binding)
# ---------------------------------------------------------------------------


def test_generic_handler_is_registered_for_the_vibecomfy_binding() -> None:
    handler = resolve_task_handler("vibecomfy")
    assert isinstance(handler, VibeComfyTaskHandler)


# ---------------------------------------------------------------------------
# Exceptional paths — full fail-closed evidence
# ---------------------------------------------------------------------------


def test_digest_mismatch_refuses_before_subprocess_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _local_spec(tmp_path, monkeypatch, workflow=SMOKE_WORKFLOW)
    # Tamper the bytes AFTER admission snapshotted the digest; the
    # declaration row is re-stamped so ONLY the handler's fences (snapshot
    # vs authority, disk bytes vs pin) can catch the drift.
    wf_path = Path(spec["workflow"]["path"])
    wf_path.write_text(json.dumps({**SMOKE_WORKFLOW, "tampered": True}))
    tampered_digest = hashlib.sha256(wf_path.read_bytes()).hexdigest()
    (tmp_path / "workflows" / "smoke_red.yaml").write_text(
        f"id: smoke_red\nworkflow_path: {wf_path}\ndigest: {tampered_digest}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        binding.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess spawned despite digest drift"),
    )
    with pytest.raises(WorkflowDigestMismatch, match="disagrees with pinned authority"):
        VibeComfyTaskHandler().execute(task=_task(spec), staging_dir=tmp_path)


def test_missing_pinned_checkout_refuses_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _local_spec(tmp_path, monkeypatch, workflow=SMOKE_WORKFLOW)
    monkeypatch.setenv("REIGH_VIBECOMFY_HOME", str(tmp_path / "absent"))
    with pytest.raises(RuntimeUnavailable, match="checkout not found"):
        VibeComfyTaskHandler().execute(task=_task(spec), staging_dir=tmp_path)


def test_malformed_workflow_refuses_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _local_spec(tmp_path, monkeypatch, workflow="{not json at all")
    # Re-stamp the snapshot digest so ONLY the malformed-bytes leg fires.
    wf_path = Path(spec["workflow"]["path"])
    digest = hashlib.sha256(wf_path.read_bytes()).hexdigest()
    spec["workflow"]["sha256"] = digest
    monkeypatch.setattr(
        binding.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess spawned despite malformed workflow"),
    )
    with pytest.raises(MalformedWorkflow, match="not valid JSON"):
        VibeComfyTaskHandler().execute(task=_task(spec), staging_dir=tmp_path)


def test_non_graph_workflow_refuses_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _local_spec(tmp_path, monkeypatch, workflow={"not": "a graph"})
    wf_path = Path(spec["workflow"]["path"])
    digest = hashlib.sha256(wf_path.read_bytes()).hexdigest()
    spec["workflow"]["sha256"] = digest
    monkeypatch.setattr(
        binding.subprocess,
        "run",
        lambda *a, **k: pytest.fail("subprocess spawned despite non-graph workflow"),
    )
    with pytest.raises(MalformedWorkflow, match="API-format graph"):
        VibeComfyTaskHandler().execute(task=_task(spec), staging_dir=tmp_path)


# ---------------------------------------------------------------------------
# Typed-port injection: t2i / i2i / edit shapes (named tests)
# ---------------------------------------------------------------------------


def test_inject_t2i_shape_prompt_seed_size(tmp_path: Path) -> None:
    workflow = json.loads(
        (Path(binding.__file__).parent / "workflows" / "z_image.json").read_text()
    )
    out = inject_ports(
        workflow,
        {"prompts": ["a red cube"], "seed": 42, "size": "512x768"},
    )
    # Prompt rides the first CLIPTextEncode; seed lands on the KSampler;
    # size splits onto the EmptySD3LatentImage latent.
    assert out["5"]["inputs"]["text"] == "a red cube"
    assert out["8"]["inputs"]["seed"] == 42
    assert out["4"]["inputs"]["width"] == 512
    assert out["4"]["inputs"]["height"] == 768
    # The admitted graph is never mutated.
    assert workflow["5"]["inputs"]["text"] != "a red cube"


def test_inject_i2i_shape_image_strength(tmp_path: Path) -> None:
    workflow = json.loads(
        (
            Path(binding.__file__).parent
            / "workflows"
            / "z_image_img2img.json"
        ).read_text()
    )
    source = tmp_path / "source.png"
    source.write_bytes(b"png-bytes")
    out = inject_ports(
        workflow,
        {"prompt": "same cube", "image_url": str(source), "strength": 0.5},
        input_dir=tmp_path / "input",
    )
    # The image asset is copied into the checkout input dir under a
    # content-addressed name and wired to the LoadImage node.
    assert out["1"]["inputs"]["image"].startswith("astrid_image_")
    assert (tmp_path / "input" / out["1"]["inputs"]["image"]).is_file()
    assert out["10"]["inputs"]["denoise"] == 0.5
    assert out["10"]["inputs"]["seed"] == 770044821593082  # template default kept


def test_inject_edit_shape_prompt_and_negative(tmp_path: Path) -> None:
    workflow = json.loads(
        (
            Path(binding.__file__).parent
            / "workflows"
            / "qwen_image_edit.json"
        ).read_text()
    )
    source = tmp_path / "subject.png"
    source.write_bytes(b"png-bytes")
    out = inject_ports(
        workflow,
        {
            "prompt": "make it night",
            "negative_prompt": "blurry",
            "image_url": str(source),
            "seed": 7,
        },
        input_dir=tmp_path / "input",
    )
    # Edit shape: prompt rides TextEncodeQwenImageEdit (positive node 6),
    # the negative lands on the second one (node 7), the image on LoadImage.
    assert out["6"]["inputs"]["prompt"] == "make it night"
    assert out["7"]["inputs"]["prompt"] == "blurry"
    assert out["78"]["inputs"]["image"].startswith("astrid_image_")
    assert out["13"]["inputs"]["seed"] == 7


def test_supplied_port_without_target_refuses(tmp_path: Path) -> None:
    with pytest.raises(PortInjectionError, match="'seed'"):
        inject_ports(
            dict(SMOKE_WORKFLOW),
            {"seed": 5},
        )


def test_missing_image_asset_refuses(tmp_path: Path) -> None:
    with pytest.raises(PortInjectionError, match="not a readable local file"):
        inject_ports(
            {"1": {"class_type": "LoadImage", "inputs": {"image": "x.png"}}},
            {"image_url": str(tmp_path / "absent.png")},
        )


# ---------------------------------------------------------------------------
# CPU smoke determinism: 3 real-subprocess invocations
# ---------------------------------------------------------------------------


def _decoded_pixel_sha(png_path: Path) -> str:
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(png_path.read_bytes())) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def test_cpu_smoke_deterministic_across_three_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _runtime_or_skip()
    handler = VibeComfyTaskHandler()
    spec = _local_spec(tmp_path, monkeypatch, workflow=SMOKE_WORKFLOW)
    pixel_hashes = []
    for _ in range(3):
        staging = tmp_path / f"staging-{len(pixel_hashes)}"
        staging.mkdir()
        manifest = handler.execute(task=_task(spec), staging_dir=staging)
        outputs = manifest["outputs"]
        assert len(outputs) == 1
        primary = outputs[0]
        assert primary["is_primary"] is True
        png = staging / primary["path"]
        assert png.is_file()
        assert primary["bytes"] == png.stat().st_size
        pixel_hashes.append(_decoded_pixel_sha(png))
    assert len(set(pixel_hashes)) == 1, pixel_hashes


def test_handler_manifest_validates_through_kernel_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The handler manifest is accepted by the strict kernel validator."""
    _runtime_or_skip()
    from astrid.core._shared.result_manifest import validate_result_manifest

    staging = tmp_path / "staging"
    staging.mkdir()
    spec = _local_spec(tmp_path, monkeypatch, workflow=SMOKE_WORKFLOW)
    manifest = VibeComfyTaskHandler().execute(task=_task(spec), staging_dir=staging)
    validated = validate_result_manifest(manifest, staging_root=staging)
    assert len(validated.outputs) == 1
