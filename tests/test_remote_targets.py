from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from astrid.core.remote_targets import RemoteTargetError, provision_local_bare_target, resolve_target_set


def _target(oid: str) -> dict[str, str]:
    return {
        "remote_target_id": "REMOTE-TARGET:COMPONENT:ASTRID-CLIENT",
        "target_kind": "component",
        "component_id": "ASTRID-CLIENT",
        "local_repository_identity": "peteromallet/Astrid",
        "repository_identity": "peteromallet/Astrid",
        "canonical_url": "https://github.com/peteromallet/Astrid.git",
        "destination_ref_or_prefix": "refs/heads/main",
        "expected_old_oid": "NONE",
        "reviewed_source_oid": oid,
        "identity_transition_sha256": "a" * 64,
        "repository_provision_receipt_rows": "NONE",
    }


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
