from __future__ import annotations

import json
from pathlib import Path
import subprocess
import threading

import pytest

import astrid.core.remote_targets as remote_targets
from astrid.core.remote_targets import RemoteTargetError, provision_local_bare_target, resolve_target_set
from astrid.core.release_identity import framed_hash


def _target(oid: str) -> dict[str, str]:
    target = {
        "remote_target_id": "REMOTE-TARGET:COMPONENT:ASTRID-CLIENT",
        "target_kind": "component",
        "component_id": "ASTRID-CLIENT",
        "local_repository_identity": "peteromallet/Astrid",
        "repository_identity": "peteromallet/Astrid",
        "canonical_url": "https://github.com/peteromallet/Astrid.git",
        "destination_ref_or_prefix": "refs/heads/main",
        "expected_old_oid": "NONE",
        "reviewed_source_oid": oid,
        "identity_transition_sha256": "",
        "repository_provision_receipt_rows": "NONE",
    }
    target["identity_transition_sha256"] = framed_hash(
        "banodoco.local-to-canonical-repository.v1",
        [target["component_id"], target["local_repository_identity"], target["repository_identity"], target["canonical_url"], target["destination_ref_or_prefix"], oid],
    )
    return target


def _remote_fixture(tmp_path: Path) -> tuple[Path, str, str]:
    remote = tmp_path / "remote.git"
    source = tmp_path / "source"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    (source / "payload").write_text("one")
    subprocess.run(["git", "-C", str(source), "add", "payload"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "one"], check=True)
    first = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(source), "push", "-q", str(remote), "HEAD:refs/heads/main"], check=True)
    (source / "payload").write_text("two")
    subprocess.run(["git", "-C", str(source), "commit", "-qam", "two"], check=True)
    second = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(source), "push", "-q", str(remote), "HEAD:refs/heads/second"], check=True)
    return remote, first, second


def test_local_bare_provision_is_conditional_and_idempotent(tmp_path: Path):
    remote, oid, _ = _remote_fixture(tmp_path)
    subprocess.run(["git", "--git-dir", str(remote), "update-ref", "-d", "refs/heads/main"], check=True)
    target = _target(oid)
    first = resolve_target_set([target], local_bare_remotes={target["remote_target_id"]: remote}, provision=True)["targets"][0]
    assert first["repository_provision_receipt_rows"][0]["status"] == 201
    second = provision_local_bare_target(target, local_bare_remote=remote)
    assert second["repository_provision_receipt_rows"][0]["status"] == 200
    shown = subprocess.check_output(["git", "--git-dir", str(remote), "show-ref", "--hash", "refs/heads/main"], text=True).strip()
    assert shown == oid


def test_existing_different_oid_is_a_conflict_not_absent(tmp_path: Path):
    remote, _, second = _remote_fixture(tmp_path)
    with pytest.raises(RemoteTargetError, match="conflict"):
        provision_local_bare_target(_target(second), local_bare_remote=remote)


def test_target_set_preserves_publication_suffix_without_inventing_oid(tmp_path: Path):
    remote, first, _ = _remote_fixture(tmp_path)
    component = provision_local_bare_target(_target(first), local_bare_remote=remote)
    publication = {
        "remote_target_id": "REMOTE-TARGET:PUBLICATION", "target_kind": "publication", "component_id": "NONE",
        "local_repository_identity": "NONE", "repository_identity": "banodoco/banodoco-workspace-runtime",
        "canonical_url": "https://github.com/banodoco/banodoco-workspace-runtime.git",
        "destination_ref_or_prefix": "refs/tags/astrid-stage1-evidence/", "expected_old_oid": "NONE",
        "reviewed_source_oid": "NONE", "identity_transition_sha256": "NONE", "repository_provision_receipt_rows": "NONE",
    }
    result = resolve_target_set([component, publication], local_bare_remotes={component["remote_target_id"]: remote})
    assert result["targets"][-1]["destination_ref_or_prefix"].endswith("/")
    assert result["targets"][-1]["repository_provision_receipt_rows"] == "NONE"


def test_network_resolution_requires_explicit_authorized_transport():
    with pytest.raises(RemoteTargetError, match="authorized transport"):
        remote_targets.resolve_remote_target(_target("a" * 40))


def test_authorized_transport_is_the_only_network_observation_boundary():
    target = _target("a" * 40)
    observed = []

    def transport(locator, ref):
        observed.append((locator["canonical_url"], ref))
        return target["reviewed_source_oid"], 200, target["reviewed_source_oid"]

    result = remote_targets.resolve_remote_target(target, authorized_transport=transport)
    assert observed == [(target["canonical_url"], target["destination_ref_or_prefix"])]
    assert result["repository_provision_receipt_rows"][0]["status"] == 200


def test_remote_locator_binding_rejects_wrong_url_or_transition_digest():
    target = _target("a" * 40)
    wrong_url = dict(target, canonical_url="https://github.com/other/project.git")
    with pytest.raises(RemoteTargetError, match="URL"):
        remote_targets.resolve_remote_target(wrong_url, authorized_transport=lambda *_: (target["reviewed_source_oid"], 200, "ok"))
    with pytest.raises(RemoteTargetError, match="transition"):
        remote_targets.resolve_remote_target(dict(target, identity_transition_sha256="a" * 64), authorized_transport=lambda *_: (target["reviewed_source_oid"], 200, "ok"))


@pytest.mark.parametrize("status,actual", [(401, "a" * 40), (503, "a" * 40), (200, None)])
def test_authorized_transport_requires_successful_bound_result(status, actual):
    target = _target("a" * 40)
    with pytest.raises(RemoteTargetError):
        remote_targets.resolve_remote_target(target, authorized_transport=lambda *_: (actual, status, "response"))


def test_provision_postflight_mismatch_fails_closed(tmp_path: Path, monkeypatch):
    remote, oid, other = _remote_fixture(tmp_path)
    subprocess.run(["git", "--git-dir", str(remote), "update-ref", "-d", "refs/heads/main"], check=True)
    target = _target(oid)
    original_probe = remote_targets._local_oid
    probes = iter([None, None, other])
    monkeypatch.setattr(remote_targets, "_local_oid", lambda path, ref: next(probes, original_probe(path, ref)))
    with pytest.raises(RemoteTargetError, match="postflight"):
        provision_local_bare_target(target, local_bare_remote=remote)


def test_local_bare_creation_uses_compare_and_swap_under_conflicting_race(tmp_path: Path, monkeypatch):
    remote, first, second = _remote_fixture(tmp_path)
    subprocess.run(["git", "--git-dir", str(remote), "update-ref", "-d", "refs/heads/main"], check=True)
    barrier = threading.Barrier(2)
    calls = threading.local()
    original_probe = remote_targets._local_oid

    def synchronized_probe(path, ref):
        count = getattr(calls, "count", 0) + 1
        calls.count = count
        if count == 1:
            barrier.wait()
        return original_probe(path, ref)

    monkeypatch.setattr(remote_targets, "_local_oid", synchronized_probe)
    targets = [_target(first), _target(second)]
    results = []

    def provision(target):
        try:
            provision_local_bare_target(target, local_bare_remote=remote)
        except Exception as exc:  # assert the losing creator fails closed
            return type(exc).__name__
        return "ok"

    threads = [threading.Thread(target=lambda target=target: results.append(provision(target))) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert sorted(results) == ["RemoteTargetError", "ok"]
    final = subprocess.check_output(["git", "--git-dir", str(remote), "show-ref", "--hash", "refs/heads/main"], text=True).strip()
    assert final in {first, second}
