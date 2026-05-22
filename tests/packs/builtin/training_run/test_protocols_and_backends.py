"""Backend protocol and registry coverage for generic training runs."""

from __future__ import annotations

import inspect

import pytest

from astrid.packs.builtin.dataset_build.interfaces import ComputeBackend, RemoteExecutionBackend
from astrid.packs.builtin.training_run.compute_backends import BackendRegistryError, get_compute_backend, get_remote_execution_backend


def test_compute_and_remote_execution_protocols_stay_separate() -> None:
    compute_methods = set(ComputeBackend.__dict__)
    remote_methods = set(RemoteExecutionBackend.__dict__)

    assert {"provision", "teardown", "estimate_cost"}.issubset(compute_methods)
    assert "exec" not in compute_methods
    assert "pull_artifacts" not in compute_methods
    assert {"capabilities", "exec", "pull_artifacts"}.issubset(remote_methods)
    assert "provision" not in remote_methods

    assert "config" in inspect.signature(ComputeBackend.provision).parameters
    assert "remote_paths" in inspect.signature(RemoteExecutionBackend.pull_artifacts).parameters


def test_registry_lookup_capabilities_invalid_ids_and_cost_estimation() -> None:
    compute = get_compute_backend("runpod")
    remote = get_remote_execution_backend("runpod")

    assert compute.backend_id == "runpod"
    assert remote.backend_id == "runpod"
    assert remote.capabilities.supports_exec is True
    assert remote.capabilities.supports_artifact_pull is True
    assert remote.capabilities.supports_artifact_push is True
    estimate = compute.estimate_cost({"gpu_type": "NVIDIA RTX 6000 Ada Generation", "max_gpu_hours": 2})
    assert estimate.estimated_cost_usd == 1.58
    assert estimate.details["pricing_source"] == "pinned_training_run_rates"

    with pytest.raises(BackendRegistryError, match="available: runpod"):
        get_compute_backend("missing")
    with pytest.raises(BackendRegistryError, match="available: runpod"):
        get_remote_execution_backend("missing")
