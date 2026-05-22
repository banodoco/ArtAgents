"""RunPod artifact pull command construction and local checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from astrid.packs.external.runpod import run as runpod_run


def _handle() -> dict:
    return {
        "pod_id": "pod-abc123",
        "ssh": "root@1.2.3.4 -p 2222",
    }


def test_build_scp_pull_command_uses_existing_pod_handle_shape(tmp_path: Path) -> None:
    cmd = runpod_run._build_scp_pull_command(
        _handle(),
        remote_path="/workspace/output/checkpoint.safetensors",
        local_dir=tmp_path,
        ssh_key="/tmp/pod_key/id",
    )

    assert cmd == [
        "scp",
        "-r",
        "-P",
        "2222",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "IdentitiesOnly=yes",
        "-i",
        "/tmp/pod_key/id",
        "root@1.2.3.4:/workspace/output/checkpoint.safetensors",
        str(tmp_path),
    ]


def test_pull_writes_manifest_only_when_local_artifact_exists(tmp_path: Path, monkeypatch) -> None:
    produces = tmp_path / "produces"
    produces.mkdir()
    handle_path = tmp_path / "pod_handle.json"
    handle_path.write_text(json.dumps(_handle()) + "\n", encoding="utf-8")
    local_dir = tmp_path / "local"

    calls: list[list[str]] = []

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess:
        calls.append(cmd)
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "checkpoint.safetensors").write_bytes(b"checkpoint")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(runpod_run.subprocess, "run", fake_run)

    Args = type(
        "Args",
        (),
        {
            "pod_handle": str(handle_path),
            "remote_path": ["/workspace/output/checkpoint.safetensors"],
            "local_dir": str(local_dir),
            "ssh_key": None,
        },
    )

    rc = runpod_run.cmd_pull(Args(), produces)

    assert rc == 0
    assert calls
    manifest = json.loads((produces / "artifact_pull.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert manifest["artifacts"][0]["exists"] is True
    assert manifest["artifacts"][0]["local_path"] == str(local_dir / "checkpoint.safetensors")


def test_pull_fails_if_scp_succeeds_but_expected_local_artifact_is_missing(tmp_path: Path, monkeypatch) -> None:
    produces = tmp_path / "produces"
    produces.mkdir()
    handle_path = tmp_path / "pod_handle.json"
    handle_path.write_text(json.dumps(_handle()) + "\n", encoding="utf-8")

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(runpod_run.subprocess, "run", fake_run)

    Args = type(
        "Args",
        (),
        {
            "pod_handle": str(handle_path),
            "remote_path": ["/workspace/output/missing.safetensors"],
            "local_dir": str(tmp_path / "local"),
            "ssh_key": None,
        },
    )

    rc = runpod_run.cmd_pull(Args(), produces)

    assert rc == 3
    manifest = json.loads((produces / "artifact_pull.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "missing_local"


def test_pull_directory_contents_accepts_local_dir_as_artifact_root(tmp_path: Path, monkeypatch) -> None:
    produces = tmp_path / "produces"
    produces.mkdir()
    handle_path = tmp_path / "pod_handle.json"
    handle_path.write_text(json.dumps(_handle()) + "\n", encoding="utf-8")
    local_dir = tmp_path / "samples"

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess:
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "sample.mp4").write_bytes(b"mp4")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(runpod_run.subprocess, "run", fake_run)
    Args = type(
        "Args",
        (),
        {
            "pod_handle": str(handle_path),
            "remote_path": ["/workspace/output/run/samples/."],
            "local_dir": str(local_dir),
            "ssh_key": None,
        },
    )

    rc = runpod_run.cmd_pull(Args(), produces)

    assert rc == 0
    manifest = json.loads((produces / "artifact_pull.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"][0]["local_path"] == str(local_dir)
