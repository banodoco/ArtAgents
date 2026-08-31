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
    pre = create_pre_live_identity({"ASTRID-CLIENT": astrid, "NEUTRAL-RUNTIME": runtime}, output=pre_path)
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

