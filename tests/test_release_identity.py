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
    main,
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
    remote = "https://github.com/peteromallet/Astrid.git" if name == "Astrid" else "https://github.com/banodoco/banodoco-workspace-runtime.git" if name == "runtime" else "https://github.com/example/Repo.git"
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)
    return path

def _seeds() -> dict[str, bytes]:
    from astrid.core.release_identity import PRELIVE_SEEDS
    return {seed: seed.encode() for seed in PRELIVE_SEEDS}


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
    pre = create_pre_live_identity({"ASTRID-CLIENT": checkout}, seed_outputs=_seeds())
    original = json.dumps(pre, sort_keys=True)
    bound = bind_remote_targets(pre, [{"remote_target_id": "REMOTE-TARGET:ASTRID", "target_kind": "component", "component_id": "ASTRID-CLIENT", "local_repository_identity": "peteromallet/Astrid", "repository_identity": "peteromallet/Astrid", "canonical_url": "https://github.com/peteromallet/Astrid.git", "destination_ref_or_prefix": "refs/heads/main", "expected_old_oid": "NONE", "reviewed_source_oid": "NONE", "identity_transition_sha256": "NONE", "repository_provision_receipt_rows": "NONE"}])
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
    receipt = create_pre_live_identity({"Repo": checkout}, seed_outputs=_seeds())
    receipt["pre_live_manifest"] = manifest
    from astrid.core.release_identity import _receipt_digest, verify_receipt
    receipt["receipt_sha256"] = _receipt_digest(receipt)
    with pytest.raises(ReleaseIdentityError, match="evidence cardinality"):
        verify_receipt(receipt)


def test_receipt_inside_checkout_and_locator_traversal_are_rejected(tmp_path: Path) -> None:
    checkout = _repo(tmp_path, "Astrid")
    with pytest.raises(ReleaseIdentityError, match="inside"):
        create_pre_live_identity({"ASTRID-CLIENT": checkout}, output=checkout / "receipt.json")
    pre = create_pre_live_identity({"ASTRID-CLIENT": checkout}, seed_outputs=_seeds())
    with pytest.raises(ReleaseIdentityError, match="fields"):
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
    receipt = create_pre_live_identity({"ASTRID-CLIENT": checkout}, seed_outputs=_seeds(), generator_definitions=[{"generator_id": "GEN", "component_id": "ASTRID-CLIENT", "checkout": str(checkout), "entrypoint_path": "generator.py"}], contract_bytes=b"{}", schema_manifest_bytes=b"{}")
    assert verify_receipt(receipt) == receipt["identity"]
    candidate = create_candidate_core_identity(receipt, {"ASTRID-CLIENT": checkout})
    assert verify_receipt(candidate) == candidate["identity"]

def test_installed_cli_consumes_exact_seed_directory_manifest(tmp_path: Path) -> None:
    checkout = _repo(tmp_path, "Astrid")
    seed_dir = tmp_path / "seed-bytes"; seed_dir.mkdir()
    manifest = {}
    from astrid.core.release_identity import PRELIVE_SEEDS
    for index, seed in enumerate(PRELIVE_SEEDS):
        name = f"{index:02d}.bin"; (seed_dir / name).write_bytes(seed.encode()); manifest[seed] = {"path": name, "media_type": "application/octet-stream", "producer_id": "FIXTURE-PRODUCER"}
    manifest_path = tmp_path / "seeds.json"; manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "cli-pre.json"
    assert main(["pre-live", "--component", f"ASTRID-CLIENT={checkout}", "--seed-dir", str(seed_dir), "--seed-manifest", str(manifest_path), "--output", str(output)]) == 0
    receipt = load_receipt(output)
    assert receipt["pre_live_seed_payloads"][0]["media_type"] == "application/octet-stream"
    assert receipt["pre_live_seed_payloads"][0]["producer_id"] == "FIXTURE-PRODUCER"

def test_b11_local_submodule_is_pinned_and_inside_source_root(tmp_path: Path) -> None:
    sub = _repo(tmp_path, "submodule"); checkout = _repo(tmp_path, "Astrid")
    subprocess.run(["git", "-C", str(checkout), "-c", "protocol.file.allow=always", "submodule", "add", str(sub), "vendor/sub"], check=True, stdout=subprocess.DEVNULL)
    (checkout / "generator.py").write_text("import argparse, pathlib\np=argparse.ArgumentParser(); p.add_argument('--contract'); p.add_argument('--schema-manifest'); p.add_argument('--output-root'); a=p.parse_args(); pathlib.Path(a.output_root, 'out').write_bytes(b'ok')\n")
    subprocess.run(["git", "-C", str(checkout), "add", "."], check=True); subprocess.run(["git", "-C", str(checkout), "commit", "-qm", "submodule generator"], check=True)
    row = resolve_component("ASTRID-CLIENT", checkout)
    observed = run_b11_1([row], [{"generator_id": "GEN", "component_id": "ASTRID-CLIENT", "checkout": str(checkout), "entrypoint_path": "generator.py"}], contract_bytes=b"{}", schema_manifest_bytes=b"{}")
    assert observed[0]["generator_observation_rows"][0]["output_digests"]
    outside = tmp_path.parent / "b11-outside-submodule"
    subprocess.run(["git", "-C", str(checkout), "config", "-f", ".gitmodules", "submodule.vendor/sub.url", str(outside)], check=True)
    subprocess.run(["git", "-C", str(checkout), "add", ".gitmodules"], check=True); subprocess.run(["git", "-C", str(checkout), "commit", "-qm", "malicious submodule url"], check=True)
    with pytest.raises(ReleaseIdentityError, match="approved source root"):
        run_b11_1([resolve_component("ASTRID-CLIENT", checkout)], [{"generator_id": "GEN", "component_id": "ASTRID-CLIENT", "checkout": str(checkout), "entrypoint_path": "generator.py"}], contract_bytes=b"{}", schema_manifest_bytes=b"{}")


def test_b11_rejects_generator_input_and_origin_mutation(tmp_path: Path) -> None:
    checkout = _repo(tmp_path, "Astrid")
    original = (checkout / "contract" / "schema.json").read_bytes()
    script = checkout / "generator.py"
    script.write_text(
        "import argparse, pathlib, subprocess\n"
        "p=argparse.ArgumentParser(); p.add_argument('--contract'); p.add_argument('--schema-manifest'); p.add_argument('--output-root'); a=p.parse_args()\n"
        "subprocess.run(['git', 'remote', 'add', 'origin', '/tmp/forbidden-origin'], check=False)\n"
        "subprocess.run(['git', 'push', 'origin', 'HEAD'], check=False)\n"
        "pathlib.Path(a.contract).write_text('tampered')\n"
        "pathlib.Path(a.output_root, 'out').write_bytes(b'ok')\n"
    )
    subprocess.run(["git", "-C", str(checkout), "add", "generator.py"], check=True)
    subprocess.run(["git", "-C", str(checkout), "commit", "-qm", "malicious generator"], check=True)
    with pytest.raises(ReleaseIdentityError):
        run_b11_1(
            [resolve_component("ASTRID-CLIENT", checkout)],
            [{"generator_id": "GEN", "component_id": "ASTRID-CLIENT", "checkout": str(checkout), "entrypoint_path": "generator.py"}],
            contract_bytes=b"{}", schema_manifest_bytes=b"{}",
        )
    assert (checkout / "contract" / "schema.json").read_bytes() == original
    assert subprocess.check_output(["git", "-C", str(checkout), "remote"], text=True) == "origin\n"
