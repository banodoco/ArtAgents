from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from astrid.core.release_identity import (
    ReleaseIdentityError,
    bind_remote_targets,
    create_candidate_core_identity,
    create_pre_live_identity,
    load_receipt,
    verify_receipt,
    build_prelive_manifest,
    run_b11_1,
    resolve_component,
)


def _repo(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir()
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Release Test"], check=True)
    (path / "contract").mkdir()
    (path / "contract" / "schema.json").write_text('{"version":1}\n')
    (path / "generated").mkdir()
    (path / "generated" / "client.py").write_text("CLIENT = 1\n")
    (path / "astrid-pack-manifest.yaml").write_text("capability: render\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "initial"], check=True)
    return path


def test_pre_live_and_candidate_receipts_are_reproducible(tmp_path: Path) -> None:
    astrid = _repo(tmp_path, "Astrid")
    runtime = _repo(tmp_path, "runtime")
    pre_path = tmp_path / "pre-live.json"
    pre = create_pre_live_identity({"ASTRID-CLIENT": astrid, "NEUTRAL-RUNTIME": runtime}, output=pre_path, seed_outputs={seed: seed.encode() for seed in __import__("astrid.core.release_identity", fromlist=["PRELIVE_SEEDS"]).PRELIVE_SEEDS})
    assert load_receipt(pre_path)["identity"] == pre["identity"]
    assert verify_receipt(pre) == pre["identity"]

    candidate = create_candidate_core_identity(
        pre_path,
        {"ASTRID-CLIENT": astrid, "NEUTRAL-RUNTIME": runtime},
    )
    assert verify_receipt(candidate) == candidate["identity"]
    assert candidate["candidate_core"]["pre_live_evidence_root"] == pre["identity"]
    assert candidate["candidate_core"]["release_epoch"] == "NONE"


def test_dirty_candidate_is_rejected(tmp_path: Path) -> None:
    checkout = _repo(tmp_path, "Astrid")
    (checkout / "uncommitted.txt").write_text("not released\n")
    with pytest.raises(ReleaseIdentityError, match="uncommitted"):
        create_pre_live_identity({"ASTRID-CLIENT": checkout})


def test_remote_binding_is_copy_only(tmp_path: Path) -> None:
    checkout = _repo(tmp_path, "Astrid")
    pre = create_pre_live_identity({"ASTRID-CLIENT": checkout})
    original = json.dumps(pre, sort_keys=True)
    bound = bind_remote_targets(pre, [{"remote_target_id": "REMOTE-TARGET:ASTRID", "canonical_url": "https://example.invalid/Astrid.git"}])
    assert bound["remote_targets"][0]["remote_target_id"] == "REMOTE-TARGET:ASTRID"
    assert json.dumps(pre, sort_keys=True) == original
    assert not (checkout / "remote-targets.json").exists()


def test_b11_manifest_rejects_missing_seed_bytes_and_46_rows(tmp_path: Path) -> None:
    with pytest.raises(ReleaseIdentityError, match="missing"):
        build_prelive_manifest({})
    from astrid.core.release_identity import PRELIVE_SEEDS
    manifest = build_prelive_manifest({seed: seed.encode() for seed in PRELIVE_SEEDS})
    manifest["evidence_rows"].pop()
    manifest["manifest_sha256"] = __import__("astrid.core.release_identity", fromlist=["framed_hash"]).framed_hash(
        "banodoco.pre-live-manifest.v1", {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    # The full receipt verifier is intentionally the final authority; a
    # manifest with 46 rows must not become valid merely by rehashing it.
    checkout = _repo(tmp_path, "Repo")
    receipt = create_pre_live_identity({"Repo": checkout})
    receipt["pre_live_manifest"] = manifest
    from astrid.core.release_identity import _receipt_digest, verify_receipt
    receipt["receipt_sha256"] = _receipt_digest(receipt)
    with pytest.raises(ReleaseIdentityError, match="evidence cardinality"):
        verify_receipt(receipt)


def test_receipt_inside_checkout_and_locator_traversal_are_rejected(tmp_path: Path) -> None:
    checkout = _repo(tmp_path, "Astrid")
    with pytest.raises(ReleaseIdentityError, match="inside"):
        create_pre_live_identity({"ASTRID-CLIENT": checkout}, output=checkout / "receipt.json")
    pre = create_pre_live_identity({"ASTRID-CLIENT": checkout})
    with pytest.raises(ReleaseIdentityError, match="HTTPS"):
        bind_remote_targets(pre, [{"remote_target_id": "x", "canonical_url": "file:///tmp/x"}])


def test_b11_runs_declared_generator_twice(tmp_path: Path) -> None:
    checkout = _repo(tmp_path, "Astrid")
    script = checkout / "generator.py"
    script.write_text("import argparse, pathlib\np=argparse.ArgumentParser(); p.add_argument('--contract'); p.add_argument('--schema-manifest'); p.add_argument('--output-root'); a=p.parse_args(); pathlib.Path(a.output_root, 'out.bin').write_bytes(b'\\x00\\xff')\n")
    subprocess.run(["git", "-C", str(checkout), "add", "generator.py"], check=True)
    subprocess.run(["git", "-C", str(checkout), "commit", "-qm", "generator"], check=True)
    row = resolve_component("ASTRID-CLIENT", checkout)
    observed = run_b11_1([row], [{"generator_id": "GEN", "component_id": "ASTRID-CLIENT", "checkout": str(checkout), "entrypoint_path": "generator.py"}], contract_bytes=b"{}", schema_manifest_bytes=b"{}")
    assert observed[0]["generator_observation_rows"][0]["first_run_receipt_sha256"]
    assert observed[0]["generator_observation_rows"][0]["output_digests"] == [__import__("hashlib").sha256(b"\x00\xff").hexdigest()]
