"""Gate ② — path/import/config contract tests (Batch B7).

The in-process boot boundary (doc 03 §1.2) proven mechanically against a
fake checkout whose stub ``wgp.py`` records the exact process facts at
import time: cwd, argv, env spoofs, module file location. Plus the
real-tree import smoke — skipped with reason when the pinned dependency
closure (mmgp/torch/CUDA-class stack) is absent, never silently dropped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.wgp_bridge import (
    WgpBridgeRefused,
    ensure_wan2gp_on_path,
    rewrite_config,
    verify_config_schema_against_pin,
    wgp_session,
)

VENDORED_CHECKOUT = Path(__file__).resolve().parents[2].parent / "vendor" / "Wan2GP"

_STUB_WGP_PY = '''"""Stub wgp module: records the boundary facts at import time."""
import json
import os
import sys

server_config = {"attention_mode": "auto", "boost": 0}

_FACTS = {
    "cwd": os.getcwd(),
    "argv": list(sys.argv),
    "worker_mode": os.environ.get("WAN2GP_WORKER_MODE"),
    "worker_id": os.environ.get("WORKER_ID"),
    "file": __file__,
}
with open(os.path.join(os.path.dirname(__file__), "boundary_facts.json"), "w") as f:
    json.dump(_FACTS, f)


def generate_video(**kwargs):
    save_path = kwargs.get("save_path") or "outputs"
    os.makedirs(save_path, exist_ok=True)
    out = os.path.join(save_path, "stub_output.png")
    with open(out, "wb") as f:
        f.write(b"stub-bytes")
    return [out]
'''


def build_fake_wgp_tree(tmp_path: Path, *, name: str = "Wan2GP-fake") -> Path:
    """A minimal pinned-tree stand-in for boundary/contract tests."""
    checkout = tmp_path / name
    checkout.mkdir(parents=True, exist_ok=True)
    (checkout / "wgp.py").write_text(_STUB_WGP_PY, encoding="utf-8")
    return checkout


@pytest.fixture()
def fake_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    checkout = build_fake_wgp_tree(tmp_path)
    monkeypatch.setenv("REIGH_WGP_HOME", str(checkout))
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.wgp_bridge.WGP_CONFIG_SCHEMA",
        frozenset({"attention_mode", "boost"}),
    )
    yield checkout
    sys.modules.pop("wgp", None)  # never leak a stub into later tests


# ---------------------------------------------------------------------------
# ensure_wan2gp_on_path
# ---------------------------------------------------------------------------


def test_ensure_wan2gp_on_path_inserts_front_and_is_idempotent(
    tmp_path: Path,
) -> None:
    checkout = build_fake_wgp_tree(tmp_path)
    before = list(sys.path)
    try:
        assert ensure_wan2gp_on_path(checkout) is True
        assert sys.path[0] == str(checkout)
        assert ensure_wan2gp_on_path(checkout) is False
        assert sys.path.count(str(checkout)) == 1
    finally:
        sys.path.remove(str(checkout))
        assert sys.path == before


# ---------------------------------------------------------------------------
# The session boundary: cwd / argv spoof / env spoofs / import
# ---------------------------------------------------------------------------


def test_session_boundary_sets_cwd_argv_env_and_imports_wgp(
    fake_checkout: Path,
) -> None:
    cwd_before = Path.cwd()
    argv_before = list(sys.argv)
    with wgp_session() as session:
        assert session.checkout == fake_checkout.resolve()
        assert session.wgp_module.server_config["attention_mode"] == "auto"
        facts = json.loads((fake_checkout / "boundary_facts.json").read_text(encoding="utf-8"))
        # The recorded import-time facts ARE the reigh-worker contract.
        assert Path(facts["cwd"]) == fake_checkout.resolve()
        assert facts["argv"] == ["worker.py"]
        assert facts["worker_mode"] == "true"
        assert facts["worker_id"]  # spoofed, not inherited-empty
        assert Path(facts["file"]).parent == fake_checkout.resolve()
    assert Path.cwd() == cwd_before
    assert sys.argv == argv_before
    assert str(fake_checkout.resolve()) not in sys.path


def test_boundary_restores_process_state_after_body_exception(
    fake_checkout: Path,
) -> None:
    cwd_before = Path.cwd()
    argv_before = list(sys.argv)
    watched = ("WAN2GP_WORKER_MODE", "WORKER_ID")
    env_before = {k: os.environ.get(k) for k in watched}
    with pytest.raises(RuntimeError), wgp_session():
        raise RuntimeError("attempt failed mid-flight")
    assert Path.cwd() == cwd_before
    assert sys.argv == argv_before
    assert {k: os.environ.get(k) for k in watched} == env_before


def test_import_stays_cached_in_process_while_boundary_state_restores(
    fake_checkout: Path,
) -> None:
    with wgp_session() as session:
        stub_file = session.wgp_module.__file__
    assert Path(stub_file).parent == fake_checkout.resolve()
    assert sys.modules.get("wgp") is not None  # in-process model: cached


# ---------------------------------------------------------------------------
# Config contract: rewrite ONLY wgp_config.json, ONLY schema keys
# ---------------------------------------------------------------------------


def test_server_config_overrides_applied_and_config_file_rewritten(
    fake_checkout: Path,
) -> None:
    overrides = {"boost": 2}
    other_files = {p.name for p in fake_checkout.iterdir()} - {"wgp.py", "boundary_facts.json"}
    with wgp_session(server_config_overrides=overrides) as session:
        # Live module mapping updated...
        assert session.wgp_module.server_config["boost"] == 2
        # ...and ONLY wgp_config.json rewritten on disk.
        config_file = fake_checkout / "wgp_config.json"
        assert config_file.is_file()
        stored = json.loads(config_file.read_text(encoding="utf-8"))
        # Fresh fake tree: no prior config file, so the rewrite carries
        # exactly the overrides (real boot merges over wgp's own
        # default-written file).
        assert stored == {"boost": 2}
    new_files = {p.name for p in fake_checkout.iterdir()} - {"wgp.py", "boundary_facts.json"}
    assert new_files - other_files == {"wgp_config.json"}


def test_override_outside_pinned_schema_refuses_typed(fake_checkout: Path) -> None:
    import astrid.core.integrations.reigh.wgp_bridge as bridge

    original_schema = bridge.WGP_CONFIG_SCHEMA
    bridge.WGP_CONFIG_SCHEMA = frozenset({"boost"})
    try:
        with pytest.raises(WgpBridgeRefused, match="outside the pinned schema"):
            rewrite_config(fake_checkout, {"totally_unknown_key": 1})
    finally:
        bridge.WGP_CONFIG_SCHEMA = original_schema


# ---------------------------------------------------------------------------
# Real vendored tree legs
# ---------------------------------------------------------------------------


def test_real_tree_schema_verification_has_zero_drift() -> None:
    if not (VENDORED_CHECKOUT / "wgp.py").is_file():  # pragma: no cover
        pytest.skip("vendored Wan2GP tree absent; T7.1 not run on this box")
    assert verify_config_schema_against_pin(VENDORED_CHECKOUT) == []


def test_real_tree_import_wgp_smoke() -> None:
    """``import wgp`` against the REAL pin inside the dependency closure.

    CUDA-class dependency leg: needs mmgp==3.7.6 + torch. Skipped WITH
    REASON on this CPU-only box — documented per stop conditions, never
    silently dropped.
    """
    if not (VENDORED_CHECKOUT / "wgp.py").is_file():  # pragma: no cover
        pytest.skip("vendored Wan2GP tree absent; T7.1 not run on this box")
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); import wgp",
        ],
        cwd=str(VENDORED_CHECKOUT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if probe.returncode != 0:  # pragma: no cover - environment-dependent
        first_line = next(
            (ln for ln in probe.stderr.splitlines() if ln.strip()),
            "unknown import failure",
        )
        pytest.skip(
            "real `import wgp` requires the pinned dependency closure "
            f"(mmgp/torch/CUDA-class stack): {first_line}"
        )
