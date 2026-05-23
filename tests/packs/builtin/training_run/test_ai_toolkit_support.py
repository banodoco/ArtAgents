"""Built-in ai-toolkit support migrated from the retired Seinfeld pack tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.packs.builtin.orchestrators.dataset_build.interfaces import ArtifactPullResult, RemoteExecResult, RunPodHandle
from astrid.packs.builtin.orchestrators.training_run.ai_toolkit.register import register_checkpoint
from astrid.packs.builtin.orchestrators.training_run.ai_toolkit.stage import preflight_stage_inputs, stage_training_inputs


class RecordingStageRemote:
    def __init__(self, *, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.calls: list[dict[str, object]] = []

    def exec(self, handle: RunPodHandle, command: list[str], config: dict[str, object]) -> RemoteExecResult:
        self.calls.append({"handle": handle, "command": list(command), "config": dict(config)})
        return RemoteExecResult(exit_code=self.exit_code, stdout="ok\n", stderr="failed\n" if self.exit_code else "", command=command)


class RecordingRegisterRemote:
    def __init__(self, *, create_checkpoint: bool = True) -> None:
        self.create_checkpoint = create_checkpoint
        self.calls: list[dict[str, object]] = []

    def pull_artifacts(
        self,
        handle: RunPodHandle,
        remote_paths: list[str],
        local_dir: Path,
        config: dict[str, object],
    ) -> ArtifactPullResult:
        self.calls.append({"handle": handle, "remote_paths": list(remote_paths), "local_dir": local_dir, "config": dict(config)})
        local_paths: list[Path] = []
        if self.create_checkpoint:
            local_dir.mkdir(parents=True, exist_ok=True)
            for remote_path in remote_paths:
                local_path = local_dir / Path(remote_path).name
                local_path.write_bytes(b"safetensors")
                local_paths.append(local_path)
        return ArtifactPullResult(local_paths=local_paths, remote_paths=list(remote_paths), metadata={"strategy": "test"})


def test_stage_preflight_rejects_missing_manifest_or_config(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    trainer_config = tmp_path / "config.yaml"
    manifest.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="config.yaml"):
        preflight_stage_inputs(manifest_path=manifest, trainer_config_path=trainer_config)


def test_stage_training_inputs_records_upload_contract(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    trainer_config = tmp_path / "trainer" / "config.yaml"
    manifest.write_text("{}\n", encoding="utf-8")
    trainer_config.parent.mkdir(parents=True)
    trainer_config.write_text("name: test\n", encoding="utf-8")
    remote = RecordingStageRemote()
    handle = RunPodHandle("pod-123", "NVIDIA RTX 6000 Ada Generation")

    result = stage_training_inputs(
        remote,
        handle,
        manifest_path=manifest,
        trainer_config_path=trainer_config,
        local_root=tmp_path / "run",
        remote_root="/workspace/custom",
        upload_mode="sftp_walk",
        excludes=["*.tmp", "cache"],
        produces_dir=tmp_path / "produces",
        timeout=120,
    )

    assert result.remote_root == "/workspace/custom"
    assert result.local_root == (tmp_path / "run").resolve()
    assert result.exec_result.exit_code == 0
    assert len(remote.calls) == 1
    config = remote.calls[0]["config"]
    assert config["local_root"] == (tmp_path / "run").resolve()
    assert config["remote_root"] == "/workspace/custom"
    assert config["upload_mode"] == "sftp_walk"
    assert config["excludes"] == "*.tmp,cache"
    assert config["timeout"] == 120
    assert "mkdir -p /workspace/custom/dataset /workspace/custom/output" in str(config["remote_script"])


def test_stage_training_inputs_raises_on_remote_failure(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    trainer_config = tmp_path / "config.yaml"
    manifest.write_text("{}\n", encoding="utf-8")
    trainer_config.write_text("name: test\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="ai-toolkit staging failed"):
        stage_training_inputs(
            RecordingStageRemote(exit_code=1),
            RunPodHandle("pod-123", "NVIDIA RTX 6000 Ada Generation"),
            manifest_path=manifest,
            trainer_config_path=trainer_config,
            local_root=tmp_path / "run",
            remote_root="/workspace",
        )


def test_register_checkpoint_pulls_copies_and_writes_metadata(tmp_path: Path) -> None:
    remote = RecordingRegisterRemote()
    handle = RunPodHandle("pod-123", "NVIDIA RTX 6000 Ada Generation")

    result = register_checkpoint(
        remote,
        handle,
        checkpoint_remote_path="/workspace/output/demo-final.safetensors",
        local_dir=tmp_path / "pulled",
        registry_dir=tmp_path / "registered",
        lora_id="demo-lora",
        metadata={"notes": "best identity", "checkpoint": {"step": 1500}},
        produces_dir=tmp_path / "produces",
    )

    assert remote.calls[0]["remote_paths"] == ["/workspace/output/demo-final.safetensors"]
    assert result.pulled_checkpoint_path.is_file()
    assert result.registered_lora_path == (tmp_path / "registered" / "demo-final.safetensors").resolve()
    assert result.registered_lora_path.is_file()
    payload = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["lora_id"] == "demo-lora"
    assert payload["source_checkpoint_remote_path"] == "/workspace/output/demo-final.safetensors"
    assert payload["metadata"]["notes"] == "best identity"
    assert payload["metadata"]["checkpoint"]["step"] == 1500


def test_register_checkpoint_rejects_non_safetensors_and_missing_pull(tmp_path: Path) -> None:
    handle = RunPodHandle("pod-123", "NVIDIA RTX 6000 Ada Generation")
    with pytest.raises(ValueError, match="safetensors"):
        register_checkpoint(
            RecordingRegisterRemote(),
            handle,
            checkpoint_remote_path="/workspace/output/demo-final.ckpt",
            local_dir=tmp_path / "pulled",
            registry_dir=tmp_path / "registered",
            lora_id="demo-lora",
        )

    with pytest.raises(FileNotFoundError, match="pulled checkpoint is missing"):
        register_checkpoint(
            RecordingRegisterRemote(create_checkpoint=False),
            handle,
            checkpoint_remote_path="/workspace/output/demo-final.safetensors",
            local_dir=tmp_path / "missing",
            registry_dir=tmp_path / "registered",
            lora_id="demo-lora",
        )
