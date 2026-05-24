"""RunPod executor public-surface manifest contract."""

from __future__ import annotations

from pathlib import Path

from astrid.core.executor.registry import load_default_registry as load_executor_registry
from astrid.core.orchestrator.registry import load_default_registry as load_orchestrator_registry


RUNPOD_EXECUTOR_IDS = {
    "external.runpod.provision",
    "external.runpod.exec",
    "external.runpod.pull",
    "external.runpod.teardown",
    "external.runpod.session",
}

RUNPOD_RUNTIME_MODULE = "astrid.packs.external.runpod.run"
RUNPOD_REQUIREMENT = "runpod-lifecycle>=0.3"


def test_runpod_pack_exposes_five_public_executors_including_pull() -> None:
    registry = load_executor_registry()
    discovered = {executor.id for executor in registry.list() if executor.id.startswith("external.runpod.")}

    assert discovered == RUNPOD_EXECUTOR_IDS
    assert "external.runpod.pull" in discovered

    training_run = load_orchestrator_registry().get("builtin.training_run")
    assert "external.runpod.pull" in training_run.child_executors


def test_runpod_manifest_keeps_storage_name_optional_and_session_handle_transient() -> None:
    registry = load_executor_registry()

    for executor_id in ("external.runpod.provision", "external.runpod.session"):
        executor = registry.get(executor_id)
        storage_input = next(input_ for input_ in executor.inputs if input_.name == "storage_name")
        assert storage_input.required is False

    session = registry.get("external.runpod.session")
    assert "pod_handle" not in session.graph.provides
    assert set(session.graph.provides) == {"exec_result", "artifact_dir", "cost"}


def test_runpod_exec_session_do_not_expose_requested_artifact_api() -> None:
    registry = load_executor_registry()
    requested_artifact_inputs = {"artifact_paths", "artifact_path", "remote_path", "local_dir"}

    for executor_id in ("external.runpod.exec", "external.runpod.session"):
        executor = registry.get(executor_id)
        input_names = {input_.name for input_ in executor.inputs}
        assert input_names.isdisjoint(requested_artifact_inputs)
        assert "artifact_dir" in executor.graph.provides

    pull = registry.get("external.runpod.pull")
    pull_input_names = {input_.name for input_ in pull.inputs}
    assert {"remote_path", "local_dir"} <= pull_input_names
    assert "artifact_dir" in pull.graph.provides


def test_runpod_local_command_metadata_and_requirements_are_consistent() -> None:
    registry = load_executor_registry()
    requirements_file = Path("astrid/packs/external/runpod/requirements.txt")
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert requirements == [RUNPOD_REQUIREMENT]

    for executor_id in RUNPOD_EXECUTOR_IDS:
        executor = registry.get(executor_id)

        assert executor.command is not None
        assert executor.command.argv[:3] == ("{python_exec}", "-m", RUNPOD_RUNTIME_MODULE)
        assert executor.metadata["runtime_module"] == RUNPOD_RUNTIME_MODULE
        assert executor.metadata["cli_module"] == RUNPOD_RUNTIME_MODULE
        assert executor.metadata["runtime_file"] == "run.py"
        assert executor.metadata["requirements_source"] == "requirements.txt"
        assert executor.metadata["requirements"] == [RUNPOD_REQUIREMENT]
        assert list(executor.isolation.requirements) == [RUNPOD_REQUIREMENT]
