"""The WGP binding: second ``TaskHandler`` behind the kernel protocol.

Named evidence (mirrors the B2 vibecomfy binding suite):

- **One authority per binding** — ``wgp`` resolves to exactly one
  registered factory; the same capability contract as vibecomfy.
- **Build fence before anything** — no manifest or pin disagreement
  refuses typed before conversion/import.
- **End-to-end mechanics on CPU** — through the real boundary, patchset,
  and conversion against a stub ``wgp.py``; the real generation leg is
  the documented CUDA skip.
- **Provenance stamped** — every result manifest records the build
  manifest digest that ran (doc 26).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.integrations.reigh import wgp_binding as binding
from astrid.core.integrations.reigh.wgp_binding import (
    BuildFenceMismatch,
    WgpTaskHandler,
)
from astrid.core.integrations.reigh.wgp_build import (
    BuildManifestStore,
    initial_manifest,
)
from astrid.core.task_executor.service import (
    TaskExecutorError,
    resolve_task_handler,
)

sys.path.insert(0, str(Path(__file__).parent))
from test_wgp_gate2_contracts import build_fake_wgp_tree  # noqa: E402


def _task(task_id: str, task_type: str, params: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=task_id,
        capability=task_type,
        spec={
            "schema_version": 1,
            "source_task_type": task_type,
            "params": params,
        },
    )


@pytest.fixture()
def stub_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake pinned tree + installed build manifest + isolated store."""
    checkout = build_fake_wgp_tree(tmp_path)
    monkeypatch.setenv("REIGH_WGP_HOME", str(checkout))
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.wgp_bridge.WGP_CONFIG_SCHEMA",
        frozenset({"attention_mode", "boost"}),
    )
    store_root = tmp_path / "build"
    store = BuildManifestStore(store_root)
    store.install(initial_manifest())
    monkeypatch.setenv("ASTRID_WGP_BUILD_DIR", str(store_root))
    yield checkout
    sys.modules.pop("wgp", None)


# ---------------------------------------------------------------------------
# Registration (one authority per binding)
# ---------------------------------------------------------------------------


def test_wgp_binding_is_registered_behind_the_capability_contract() -> None:
    handler = resolve_task_handler("wgp")
    assert isinstance(handler, WgpTaskHandler)
    from astrid.core.integrations.reigh.capabilities import BINDING_WGP

    assert binding.BINDING_NAME == BINDING_WGP == "wgp"


def test_double_registration_of_a_different_factory_refuses() -> None:
    from astrid.core.task_executor.service import register_task_handler

    with pytest.raises(TaskExecutorError, match="already has a registered"):
        register_task_handler("wgp", lambda: WgpTaskHandler())


# ---------------------------------------------------------------------------
# Build fence
# ---------------------------------------------------------------------------


def test_execute_without_build_manifest_refuses_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = build_fake_wgp_tree(tmp_path)
    monkeypatch.setenv("REIGH_WGP_HOME", str(checkout))
    store_root = tmp_path / "empty-store"
    store_root.mkdir()
    monkeypatch.setenv("ASTRID_WGP_BUILD_DIR", str(store_root))
    handler = WgpTaskHandler()
    with pytest.raises(TaskExecutorError, match="no Wan2GP build manifest"):
        handler.execute(task=_task("t1", "wan_2_2_t2i", {"prompt": "x"}), staging_dir=tmp_path)


def test_execute_with_pin_disagreement_refuses_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.integrations.reigh.wgp_build import BuildManifest
    from astrid.core.integrations.reigh.wgp_patches import (
        UPSTREAM_BASE_SHA,
        patchset_hash,
    )

    checkout = build_fake_wgp_tree(tmp_path)
    monkeypatch.setenv("REIGH_WGP_HOME", str(checkout))
    store_root = tmp_path / "store2"
    store = BuildManifestStore(store_root)
    store.install(
        BuildManifest(
            wan2gp_sha="b" * 40,  # NOT the vendored pin
            upstream_base=UPSTREAM_BASE_SHA,
            patchset_hash=patchset_hash(),
            worker_contract_version=1,
        )
    )
    monkeypatch.setenv("ASTRID_WGP_BUILD_DIR", str(store_root))
    handler = WgpTaskHandler()
    with pytest.raises(BuildFenceMismatch, match="vendored tree is pinned"):
        handler.execute(task=_task("t1", "wan_2_2_t2i", {"prompt": "x"}), staging_dir=tmp_path)


# ---------------------------------------------------------------------------
# End-to-end mechanics through the real boundary (stub generation)
# ---------------------------------------------------------------------------


def test_execute_end_to_end_stamps_build_provenance(stub_runtime: Path, tmp_path: Path) -> None:
    handler = WgpTaskHandler()
    staging = tmp_path / "staging"
    staging.mkdir()
    result = handler.execute(
        task=_task(
            "task-1",
            "wan_2_2_t2i",
            {"prompt": "a cat", "resolution": "832x480", "seed": 5},
        ),
        staging_dir=staging,
    )
    # Conversion contract applied end-to-end.
    assert result["inputs"]["model_preset"] == "t2v_2_2"
    # Provenance: the build manifest that RAN is stamped into completion.
    store = BuildManifestStore(Path(__import__("os").environ["ASTRID_WGP_BUILD_DIR"]))
    provenance = result["inputs"]["provenance"]
    assert provenance["kind"] == "wgp.build_manifest"
    assert provenance["sha256"] == store.require_current().digest()
    assert provenance["wan2gp_sha"] == store.require_current().wan2gp_sha
    # Universal manifest shape: one primary, hash + bytes present.
    outputs = result["outputs"]
    assert len(outputs) == 1
    primary = outputs[0]
    assert primary["is_primary"] is True
    assert primary["path"] == "stub_output.png"
    assert primary["content_hash"].startswith("sha256:")
    assert primary["bytes"] == len(b"stub-bytes")
    assert (staging / "stub_output.png").is_file()


def test_execute_normalizes_kernel_prefixed_capability_id(
    stub_runtime: Path, tmp_path: Path
) -> None:
    handler = WgpTaskHandler()
    result = handler.execute(
        task=_task(
            "task-prefixed",
            "reigh.wan_2_2_t2i",
            {"prompt": "a cat", "resolution": "832x480"},
        ),
        staging_dir=tmp_path,
    )
    assert result["inputs"]["capability_id"] == "reigh.wan_2_2_t2i"
    assert result["inputs"]["model_preset"] == "t2v_2_2"


def test_execute_runs_inside_the_patchset_boundary(
    stub_runtime: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The declared patchset applies to the live module DURING generation."""
    observed: dict = {}

    # Warm the in-process cache so the stub module is patchable here.
    from astrid.core.integrations.reigh.wgp_bridge import wgp_session

    with wgp_session():
        wgp_module = sys.modules["wgp"]
    original = wgp_module.generate_video

    def spying_generate_video(**kwargs):
        observed["model_switch_phase"] = getattr(wgp_module, "model_switch_phase", "missing")
        observed["svi_pro"] = getattr(wgp_module, "svi_pro", "missing")
        return original(**kwargs)

    monkeypatch.setattr(wgp_module, "generate_video", spying_generate_video)
    handler = WgpTaskHandler()
    handler.execute(
        task=_task(
            "task-2",
            "travel_segment",
            # phase_config is whitelisted (doc 03 §2.5); the patchset
            # carries it onto the module during generation only.
            {"prompt": "walk", "phase_config": {"steps": [1, 2]}},
        ),
        staging_dir=tmp_path,
    )
    assert observed["model_switch_phase"] == {"steps": [1, 2]}
    assert observed["svi_pro"] is False


def test_execute_restores_boundary_after_generation(stub_runtime: Path, tmp_path: Path) -> None:
    cwd_before = Path.cwd()
    argv_before = list(sys.argv)
    handler = WgpTaskHandler()
    handler.execute(
        task=_task("task-3", "wan_2_2_t2i", {"prompt": "x"}),
        staging_dir=tmp_path,
    )
    assert Path.cwd() == cwd_before
    assert sys.argv == argv_before
    assert str(stub_runtime.resolve()) not in sys.path


# ---------------------------------------------------------------------------
# Real-generation leg: documented CUDA skip
# ---------------------------------------------------------------------------


def test_real_generation_leg_is_cuda_blocked() -> None:
    """Real ``wgp.generate_video`` needs the CUDA-class stack; recorded."""
    pytest.skip(
        "real Wan2GP generation requires mmgp/torch + CUDA-class hardware; "
        "mechanics proven above against the boundary stub — per phase stop "
        "conditions this leg unblocks on a CUDA runner"
    )
