"""RunPod executor public-surface manifest contract."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from astrid.core.adapter import RunContext
from astrid.core.adapter.remote_artifact_fetch import fetch_artifacts
from astrid.core.executor.cli import main as executor_cli_main
from astrid.core.executor.registry import load_default_registry as load_executor_registry
from astrid.core.executor.runner import ExecutorRunRequest, build_executor_command
from astrid.core.orchestrator.plan_template import file_output
from astrid.core.orchestrator.registry import load_default_registry as load_orchestrator_registry
from astrid.core.task.command_render import render_task_command
from astrid.core.task.plan import Step


RUNPOD_EXECUTOR_IDS = {
    "runpod.provision",
    "runpod.exec",
    "runpod.pull",
    "runpod.teardown",
    "runpod.session",
}

RUNPOD_REQUIREMENT = "runpod-lifecycle>=0.3"


def _runpod_runtime_module(name: str) -> str:
    return f"astrid.packs.runpod.executors.{name}.run"


def test_runpod_pack_exposes_five_public_executors_including_pull() -> None:
    registry = load_executor_registry()
    discovered = {executor.id for executor in registry.list() if executor.id.startswith("runpod.")}

    assert discovered == RUNPOD_EXECUTOR_IDS
    assert "runpod.pull" in discovered

    training_run = load_orchestrator_registry().get("training.training_run")
    assert "runpod.pull" in training_run.child_executors


def test_runpod_manifest_keeps_storage_name_optional_and_session_handle_transient() -> None:
    registry = load_executor_registry()

    for executor_id in ("runpod.provision", "runpod.session"):
        executor = registry.get(executor_id)
        storage_input = next(input_ for input_ in executor.inputs if input_.name == "storage_name")
        assert storage_input.required is False

    session = registry.get("runpod.session")
    assert "pod_handle" not in session.graph.provides
    assert set(session.graph.provides) == {"exec_result", "artifact_dir", "cost"}


def test_runpod_exec_session_do_not_expose_requested_artifact_api() -> None:
    registry = load_executor_registry()
    requested_artifact_inputs = {"artifact_paths", "artifact_path", "remote_path", "local_dir"}

    for executor_id in ("runpod.exec", "runpod.session"):
        executor = registry.get(executor_id)
        input_names = {input_.name for input_ in executor.inputs}
        assert input_names.isdisjoint(requested_artifact_inputs)
        assert "artifact_dir" in executor.graph.provides

    pull = registry.get("runpod.pull")
    pull_input_names = {input_.name for input_ in pull.inputs}
    assert {"remote_path", "local_dir"} <= pull_input_names
    assert "artifact_dir" in pull.graph.provides


def test_runpod_local_command_metadata_and_requirements_are_consistent() -> None:
    registry = load_executor_registry()
    requirements_file = Path("astrid/packs/runpod/executors/provision/requirements.txt")
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert requirements == [RUNPOD_REQUIREMENT]

    for executor_id in RUNPOD_EXECUTOR_IDS:
        executor = registry.get(executor_id)
        runtime_module = _runpod_runtime_module(executor_id.split(".", 1)[1])

        assert executor.command is not None
        assert executor.command.argv[:3] == ("{python_exec}", "-m", runtime_module)
        assert executor.metadata["runtime_module"] == runtime_module
        assert executor.metadata["cli_module"] == runtime_module
        assert executor.metadata["runtime_file"] == "run.py"
        assert executor.metadata["requirements_source"] == "requirements.txt"
        assert executor.metadata["requirements"] == [RUNPOD_REQUIREMENT]
        assert list(executor.isolation.requirements) == [RUNPOD_REQUIREMENT]


def test_runpod_declared_inputs_expand_to_ordered_downstream_flags(tmp_path: Path) -> None:
    registry = load_executor_registry()

    provision = build_executor_command(
        ExecutorRunRequest(
            "runpod.provision",
            out=tmp_path / "provision",
            inputs={
                "gpu_type": "NVIDIA RTX 4090",
                "storage_name": "astrid-storage",
                "max_runtime_seconds": 1200,
                "name_prefix": "astrid",
                "image": "example/image:tag",
                "container_disk_gb": 40,
                "datacenter_id": "EU-RO-1",
                "ports": "8888/http,22/tcp",
            },
            python_exec="/opt/python",
        ),
        registry,
    )
    assert provision == (
        "/opt/python",
        "-m",
        _runpod_runtime_module("provision"),
        "provision",
        "--produces-dir",
        str((tmp_path / "provision" / "produces").resolve()),
        "--gpu-type",
        "NVIDIA RTX 4090",
        "--storage-name",
        "astrid-storage",
        "--max-runtime-seconds",
        "1200",
        "--name-prefix",
        "astrid",
        "--image",
        "example/image:tag",
        "--container-disk-gb",
        "40",
        "--datacenter-id",
        "EU-RO-1",
        "--ports",
        "8888/http,22/tcp",
    )

    exec_command = build_executor_command(
        ExecutorRunRequest(
            "runpod.exec",
            out=tmp_path / "exec",
            inputs={
                "pod_handle": "pod_handle.json",
                "local_root": "workspace",
                "remote_root": "/workspace",
                "remote_script": "run.sh",
                "timeout": 60,
                "upload_mode": "tarball",
                "excludes": "*.tmp",
            },
            python_exec="/opt/python",
        ),
        registry,
    )
    assert exec_command[-14:] == (
        "--pod-handle",
        "pod_handle.json",
        "--local-root",
        "workspace",
        "--remote-root",
        "/workspace",
        "--remote-script",
        "run.sh",
        "--timeout",
        "60",
        "--upload-mode",
        "tarball",
        "--excludes",
        "*.tmp",
    )


def test_runpod_optional_inputs_are_omitted_and_pull_remote_path_repeats_in_order(
    tmp_path: Path,
) -> None:
    registry = load_executor_registry()

    provision = build_executor_command(
        ExecutorRunRequest(
            "runpod.provision",
            out=tmp_path / "provision",
            inputs={},
            python_exec="/opt/python",
        ),
        registry,
    )
    assert provision == (
        "/opt/python",
        "-m",
        _runpod_runtime_module("provision"),
        "provision",
        "--produces-dir",
        str((tmp_path / "provision" / "produces").resolve()),
    )

    pull = build_executor_command(
        ExecutorRunRequest(
            "runpod.pull",
            out=tmp_path / "pull",
            inputs={
                "pod_handle": "pod.json",
                "remote_path": ["/remote/a.txt", "/remote/b.txt"],
                "local_dir": "downloads",
            },
            python_exec="/opt/python",
        ),
        registry,
    )
    assert pull[-8:] == (
        "--pod-handle",
        "pod.json",
        "--remote-path",
        "/remote/a.txt",
        "--remote-path",
        "/remote/b.txt",
        "--local-dir",
        "downloads",
    )


def _dry_run_stdout(argv: list[str]) -> str:
    out = StringIO()
    err = StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = executor_cli_main(argv)
    assert rc == 0, err.getvalue()
    # Command echo goes to stderr (T1); return combined so assertions on command
    # content continue to work regardless of which stream carries the echo.
    return (err.getvalue() + out.getvalue()).strip()


def test_runpod_dry_run_forwards_supplied_flags_and_omits_absent_optional_flags(
    tmp_path: Path,
) -> None:
    base = ["run", "--python-exec", "/opt/python"]

    provision = _dry_run_stdout([
        *base,
        "runpod.provision",
        "--out",
        str(tmp_path / "provision"),
        "--input",
        "gpu_type=NVIDIA L40S",
        "--input",
        "image=example/image:tag",
        "--dry-run",
    ])
    assert "--gpu-type 'NVIDIA L40S'" in provision
    assert "--image example/image:tag" in provision
    assert "--storage-name" not in provision
    assert "--ports" not in provision

    exec_out = _dry_run_stdout([
        *base,
        "runpod.exec",
        "--out",
        str(tmp_path / "exec"),
        "--input",
        "pod_handle=pod.json",
        "--input",
        "local_root=workspace",
        "--input",
        "remote_root=/workspace",
        "--input",
        "remote_script=run.sh",
        "--dry-run",
    ])
    assert "--pod-handle pod.json" in exec_out
    assert "--local-root workspace" in exec_out
    assert "--remote-root /workspace" in exec_out
    assert "--remote-script run.sh" in exec_out
    assert "--timeout" not in exec_out
    assert "--upload-mode" not in exec_out

    pull = _dry_run_stdout([
        *base,
        "runpod.pull",
        "--out",
        str(tmp_path / "pull"),
        "--input",
        "pod_handle=pod.json",
        "--input",
        "remote_path=/remote/a.txt",
        "--input",
        "remote_path=/remote/b.txt",
        "--input",
        "local_dir=downloads",
        "--dry-run",
    ])
    assert pull.count("--remote-path") == 2
    assert "--remote-path /remote/a.txt --remote-path /remote/b.txt" in pull
    assert "--local-dir downloads" in pull

    teardown = _dry_run_stdout([
        *base,
        "runpod.teardown",
        "--out",
        str(tmp_path / "teardown"),
        "--input",
        "pod_handle=pod.json",
        "--dry-run",
    ])
    assert "--pod-handle pod.json" in teardown
    assert "--keep-storage" not in teardown

    session = _dry_run_stdout([
        *base,
        "runpod.session",
        "--out",
        str(tmp_path / "session"),
        "--input",
        "gpu_type=NVIDIA L40S",
        "--input",
        "local_root=workspace",
        "--input",
        "remote_root=/workspace",
        "--input",
        "remote_script=run.sh",
        "--dry-run",
    ])
    assert "--gpu-type 'NVIDIA L40S'" in session
    assert "--local-root workspace" in session
    assert "--remote-root /workspace" in session
    assert "--remote-script run.sh" in session
    assert "--storage-name" not in session
    assert "--timeout" not in session


def test_runpod_remote_artifact_smoke_contract_is_mocked_by_default(
    tmp_path: Path,
) -> None:
    """Offline smoke for the generic manifest contract used by live RunPod.

    Live execution is opt-in: CI only proves the command/manifest/fetch shape,
    including ordered repeated pull paths, without requiring credentials or GPU
    spend.
    """

    assert not (
        os.environ.get("RUNPOD_API_KEY")
        and os.environ.get("ASTRID_LIVE_RUNPOD_SMOKE") == "1"
    )

    source_artifact = tmp_path / "remote" / "result.txt"
    source_artifact.parent.mkdir(parents=True)
    source_artifact.write_text("remote result\n", encoding="utf-8")
    checksum = hashlib.sha256(source_artifact.read_bytes()).hexdigest()

    step = Step(
        id="runpod_smoke",
        adapter="remote-artifact",
        command=(
            "python3 -m astrid executors run runpod.session "
            "--out {produces_root} "
            "--input gpu_type=NVIDIA_L40S "
            "--input local_root=. "
            "--input remote_root=/workspace "
            "--input remote_script=smoke.sh"
        ),
        produces=(file_output("result", "result.txt", checksum=checksum),),
    )
    rendered = render_task_command(
        step,
        slug="demo",
        run_id="run-smoke",
        project_root=tmp_path,
        plan_step_path=("remote", "runpod_smoke"),
    )
    assert rendered.canonical_argv[:6] == (
        "python3",
        "-m",
        "astrid",
        "executors",
        "run",
        "runpod.session",
    )
    assert "--out" in rendered.canonical_argv
    assert str(rendered.produces_root) in rendered.canonical_argv
    assert rendered.task_env["ASTRID_TASK_STEP_ID"] == "remote/runpod_smoke"

    run_ctx = RunContext(
        slug="demo",
        run_id="run-smoke",
        project_root=tmp_path,
        plan_step_path=("remote", "runpod_smoke"),
        step_version=1,
        canonical_command=rendered.canonical_command,
        canonical_argv=rendered.canonical_argv,
        display_command=rendered.display_command,
        task_env=rendered.task_env,
        produces_root=rendered.produces_root,
    )
    manifest = {
        "result.txt": {
            "path": "result.txt",
            "source": str(source_artifact),
            "sha256": checksum,
            "provider": "runpod",
        }
    }
    result = fetch_artifacts(step, run_ctx, manifest=manifest)
    assert result.status == "completed"
    assert result.fetched == ["result.txt"]
    assert (rendered.produces_root / "result.txt").read_text(encoding="utf-8") == "remote result\n"
    fetch_state = json.loads((rendered.produces_root.parent / "fetch_state.json").read_text(encoding="utf-8"))
    assert fetch_state["checksums"]["result.txt"] == checksum

    pull = build_executor_command(
        ExecutorRunRequest(
            "runpod.pull",
            out=tmp_path / "pull",
            inputs={
                "pod_handle": "pod_handle.json",
                "remote_path": ["/workspace/out/result.txt", "/workspace/out/log.txt"],
                "local_dir": str(tmp_path / "downloads"),
            },
            python_exec="python3",
        ),
        load_executor_registry(),
    )
    remote_path_flags = [
        pull[index + 1] for index, token in enumerate(pull) if token == "--remote-path"
    ]
    assert remote_path_flags == ["/workspace/out/result.txt", "/workspace/out/log.txt"]
