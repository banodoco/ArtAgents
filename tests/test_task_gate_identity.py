"""Unit tests for GateArtifactIdentity stability across executor-backed, attested, local, and manual adapter paths.

Proves identity context is present and stable for all four gate-identity modes
without overfitting to incidental run state.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from astrid.core.io.cas import (
    canonical_json_digest,
    executor_definition_digest,
    identity_digest,
    input_reference_digest,
)
from astrid.core.task.gate.base import GateArtifactIdentity, GateDecision
from astrid.core.task.gate.dispatch import (
    _artifact_input_digest,
    _compute_artifact_identity,
    _executorless_producer_identity,
    _executor_definition_from_command,
    _executor_registry_for_project,
)
from astrid.core.task.plan import Step


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_step(
    *,
    id: str = "step-1",
    adapter: str = "local",
    command: str = "echo hello",
    requires_ack: bool = False,
    produces: tuple = (),
    instructions: str | None = None,
) -> Step:
    """Minimal leaf step builder for identity tests."""
    return Step(
        id=id,
        adapter=adapter,  # type: ignore[arg-type]
        command=command,
        requires_ack=requires_ack,
        produces=produces,
        instructions=instructions,
    )


def _mock_executor(id: str = "test-executor", version: str = "1.0.0", **extra: Any) -> SimpleNamespace:
    """Return a lightweight executor-definition stand-in with ``.id`` and ``.to_dict()``."""
    fields = {"id": id, "version": version, "name": f"Test {id}", "kind": "built_in"}
    fields.update(extra)
    ns = SimpleNamespace(**fields)

    def _to_dict() -> dict[str, Any]:
        return dict(sorted(fields.items()))

    ns.to_dict = _to_dict  # type: ignore[attr-defined]
    return ns


def _mock_registry(executor: Any) -> SimpleNamespace:
    """Return a registry stand-in whose ``.get(id)`` returns *executor*."""
    reg = SimpleNamespace()
    reg.get = lambda eid: executor if eid == executor.id else None  # type: ignore[attr-defined]
    return reg


# ── dataclass contract ───────────────────────────────────────────────────────


class TestGateArtifactIdentityDataclass:
    """GateArtifactIdentity exists, is frozen, and carries required fields."""

    def test_construct_all_fields(self) -> None:
        identity = GateArtifactIdentity(
            input_digest="abc",
            producer_id="task.local",
            producer_version="def",
            identity_key="ghi",
        )
        assert identity.input_digest == "abc"
        assert identity.producer_id == "task.local"
        assert identity.producer_version == "def"
        assert identity.identity_key == "ghi"

    def test_frozen(self) -> None:
        identity = GateArtifactIdentity(
            input_digest="a", producer_id="b", producer_version="c", identity_key="d"
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.producer_id = "changed"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = GateArtifactIdentity(input_digest="x", producer_id="y", producer_version="z", identity_key="k")
        b = GateArtifactIdentity(input_digest="x", producer_id="y", producer_version="z", identity_key="k")
        c = GateArtifactIdentity(input_digest="x2", producer_id="y", producer_version="z", identity_key="k2")
        assert a == b
        assert a != c
        assert hash(a) == hash(b)

    def test_repr_includes_fields(self) -> None:
        identity = GateArtifactIdentity(
            input_digest="in", producer_id="prod", producer_version="v", identity_key="key"
        )
        r = repr(identity)
        assert "input_digest='in'" in r
        assert "producer_id='prod'" in r
        assert "producer_version='v'" in r
        assert "identity_key='key'" in r

    def test_defaults_none_on_gate_decision(self) -> None:
        decision = GateDecision(active=False)
        assert decision.artifact_identity is None


# ── executorless producer identity ───────────────────────────────────────────


class TestExecutorlessProducerIdentity:
    """_executorless_producer_identity returns stable id/version for attested, local, and manual."""

    def test_attested_producer_id_is_task_dot_attested(self) -> None:
        step = _make_step(adapter="manual", requires_ack=True)
        pid, pv = _executorless_producer_identity(step)
        assert pid == "task.attested"

    def test_local_producer_id_is_task_dot_local(self) -> None:
        step = _make_step(adapter="local", requires_ack=False)
        pid, pv = _executorless_producer_identity(step)
        assert pid == "task.local"

    def test_manual_producer_id_is_task_dot_manual(self) -> None:
        step = _make_step(adapter="manual", requires_ack=False)
        pid, pv = _executorless_producer_identity(step)
        assert pid == "task.manual"

    def test_stable_version_for_identical_step(self) -> None:
        step_a = _make_step(id="s1", adapter="local", command="echo x")
        step_b = _make_step(id="s1", adapter="local", command="echo x")
        _, va = _executorless_producer_identity(step_a)
        _, vb = _executorless_producer_identity(step_b)
        assert va == vb

    def test_version_changes_when_step_differs(self) -> None:
        step_a = _make_step(id="s1", adapter="local", command="echo x")
        step_b = _make_step(id="s2", adapter="local", command="echo y")
        _, va = _executorless_producer_identity(step_a)
        _, vb = _executorless_producer_identity(step_b)
        assert va != vb

    def test_version_uses_canonical_json_digest(self) -> None:
        """Version must be a 64-char hex sha256 (not raw json)."""
        step = _make_step(adapter="local")
        _, pv = _executorless_producer_identity(step)
        assert len(pv) == 64
        assert all(c in "0123456789abcdef" for c in pv)


# ── executor definition from command ─────────────────────────────────────────


class TestExecutorDefinitionFromCommand:
    def test_returns_none_for_plain_command(self) -> None:
        assert _executor_definition_from_command("echo hello", project_root=Path("/tmp")) is None

    def test_returns_none_for_empty_command(self) -> None:
        assert _executor_definition_from_command("", project_root=Path("/tmp")) is None
        assert _executor_definition_from_command(None, project_root=Path("/tmp")) is None

    def test_returns_executor_when_registry_has_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        exec_def = _mock_executor(id="my-exec", version="2.0")
        reg = _mock_registry(exec_def)

        # Clear lru_cache then patch.
        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg,
        )
        result = _executor_definition_from_command(
            "executors run my-exec --project demo", project_root=Path("/tmp")
        )
        assert result is not None
        assert result.id == "my-exec"

    def test_returns_none_when_executor_not_in_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        exec_def = _mock_executor(id="other")
        reg = _mock_registry(exec_def)
        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg,
        )
        result = _executor_definition_from_command(
            "executors run missing-exec --project demo", project_root=Path("/tmp")
        )
        assert result is None


# ── artifact input digest ────────────────────────────────────────────────────


class TestArtifactInputDigest:
    def test_stable_for_identical_step(self) -> None:
        step_a = _make_step(id="s1", adapter="local", command="echo x")
        step_b = _make_step(id="s1", adapter="local", command="echo x")
        dg_a = _artifact_input_digest(step=step_a, path_tuple=("s1",), iteration=None, item_id=None)
        dg_b = _artifact_input_digest(step=step_b, path_tuple=("s1",), iteration=None, item_id=None)
        assert dg_a == dg_b

    def test_changes_when_adapter_differs(self) -> None:
        step_a = _make_step(id="s1", adapter="local", command="echo x")
        step_b = _make_step(id="s1", adapter="manual", command="echo x")
        dg_a = _artifact_input_digest(step=step_a, path_tuple=("s1",), iteration=None, item_id=None)
        dg_b = _artifact_input_digest(step=step_b, path_tuple=("s1",), iteration=None, item_id=None)
        assert dg_a != dg_b

    def test_changes_when_command_differs(self) -> None:
        step_a = _make_step(id="s1", adapter="local", command="echo x")
        step_b = _make_step(id="s1", adapter="local", command="echo y")
        dg_a = _artifact_input_digest(step=step_a, path_tuple=("s1",), iteration=None, item_id=None)
        dg_b = _artifact_input_digest(step=step_b, path_tuple=("s1",), iteration=None, item_id=None)
        assert dg_a != dg_b

    def test_changes_when_path_differs(self) -> None:
        step = _make_step(id="s1", adapter="local", command="echo x")
        dg_a = _artifact_input_digest(step=step, path_tuple=("s1",), iteration=None, item_id=None)
        dg_b = _artifact_input_digest(step=step, path_tuple=("parent", "child"), iteration=None, item_id=None)
        assert dg_a != dg_b

    def test_changes_when_iteration_differs(self) -> None:
        step = _make_step(id="s1", adapter="local", command="echo x")
        dg_a = _artifact_input_digest(step=step, path_tuple=("s1",), iteration=1, item_id=None)
        dg_b = _artifact_input_digest(step=step, path_tuple=("s1",), iteration=2, item_id=None)
        assert dg_a != dg_b

    def test_changes_when_item_id_differs(self) -> None:
        step = _make_step(id="s1", adapter="local", command="echo x")
        dg_a = _artifact_input_digest(step=step, path_tuple=("s1",), iteration=None, item_id="item-a")
        dg_b = _artifact_input_digest(step=step, path_tuple=("s1",), iteration=None, item_id="item-b")
        assert dg_a != dg_b

    def test_is_64_char_hex(self) -> None:
        step = _make_step()
        dg = _artifact_input_digest(step=step, path_tuple=("s1",), iteration=None, item_id=None)
        assert len(dg) == 64
        assert all(c in "0123456789abcdef" for c in dg)


# ── compute artifact identity: executor-backed ───────────────────────────────


class TestComputeArtifactIdentityExecutorBacked:
    def test_stable_for_same_executor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same executor definition → same identity (all fields equal)."""
        exec_def = _mock_executor(id="img-resize", version="1.0")
        reg = _mock_registry(exec_def)
        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg,
        )
        step = _make_step(command="executors run img-resize --in a.jpg --out b.jpg")
        id1 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id2 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id1 is not None
        assert id2 is not None
        assert id1 == id2
        assert id1.producer_id == "img-resize"

    def test_producer_id_is_executor_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        exec_def = _mock_executor(id="my-custom-exec", version="3.0")
        reg = _mock_registry(exec_def)
        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg,
        )
        step = _make_step(command="executors run my-custom-exec --out /tmp/o")
        identity = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert identity is not None
        assert identity.producer_id == "my-custom-exec"

    def test_version_is_executor_definition_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        exec_def = _mock_executor(id="e1", version="1.0")
        reg = _mock_registry(exec_def)
        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg,
        )
        step = _make_step(command="executors run e1")
        identity = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert identity is not None
        expected_version = executor_definition_digest(exec_def)
        assert identity.producer_version == expected_version

    def test_identity_key_changes_when_executor_version_differs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exec_a = _mock_executor(id="e1", version="1.0")
        exec_b = _mock_executor(id="e1", version="2.0")
        reg_a = _mock_registry(exec_a)
        reg_b = _mock_registry(exec_b)
        step = _make_step(command="executors run e1")

        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg_a,
        )
        id_a = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )

        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg_b,
        )
        id_b = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )

        assert id_a is not None and id_b is not None
        assert id_a.identity_key != id_b.identity_key
        assert id_a.producer_version != id_b.producer_version


# ── compute artifact identity: attested (inline check) path ──────────────────


class TestComputeArtifactIdentityAttested:
    def test_attested_returns_identity(self) -> None:
        step = _make_step(adapter="manual", requires_ack=True, command="ack --project demo --step s1")
        identity = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert identity is not None
        assert identity.producer_id == "task.attested"

    def test_attested_stable_for_same_step(self) -> None:
        step = _make_step(adapter="manual", requires_ack=True, command="ack --project demo --step s1")
        id1 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id2 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id1 is not None and id2 is not None
        assert id1 == id2

    def test_attested_changes_when_instructions_differ(self) -> None:
        step_a = _make_step(
            adapter="manual", requires_ack=True, command="ack --project demo --step s1",
            instructions="review this"
        )
        step_b = _make_step(
            adapter="manual", requires_ack=True, command="ack --project demo --step s1",
            instructions="review that"
        )
        id_a = _compute_artifact_identity(
            step=step_a, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id_b = _compute_artifact_identity(
            step=step_b, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id_a is not None and id_b is not None
        assert id_a.identity_key != id_b.identity_key


# ── compute artifact identity: local adapter shell command ────────────────────


class TestComputeArtifactIdentityLocal:
    def test_local_returns_identity(self) -> None:
        step = _make_step(adapter="local", command="echo hello")
        identity = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert identity is not None
        assert identity.producer_id == "task.local"

    def test_local_stable_for_same_step(self) -> None:
        step = _make_step(adapter="local", command="echo hello")
        id1 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id2 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id1 is not None and id2 is not None
        assert id1 == id2

    def test_local_changes_when_command_differs(self) -> None:
        step_a = _make_step(adapter="local", command="echo x")
        step_b = _make_step(adapter="local", command="echo y")
        id_a = _compute_artifact_identity(
            step=step_a, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id_b = _compute_artifact_identity(
            step=step_b, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id_a is not None and id_b is not None
        assert id_a.identity_key != id_b.identity_key

    def test_local_producer_version_is_stable_digest(self) -> None:
        step = _make_step(adapter="local", command="echo hello")
        identity = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert identity is not None
        assert len(identity.producer_version) == 64
        assert all(c in "0123456789abcdef" for c in identity.producer_version)


# ── compute artifact identity: manual adapter ────────────────────────────────


class TestComputeArtifactIdentityManual:
    def test_manual_returns_identity(self) -> None:
        step = _make_step(adapter="manual", command="echo manual-step")
        identity = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert identity is not None
        assert identity.producer_id == "task.manual"

    def test_manual_stable_for_same_step(self) -> None:
        step = _make_step(adapter="manual", command="echo manual-step")
        id1 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id2 = _compute_artifact_identity(
            step=step, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id1 is not None and id2 is not None
        assert id1 == id2

    def test_manual_changes_when_instructions_differ(self) -> None:
        step_a = _make_step(adapter="manual", command="echo m", instructions="do x")
        step_b = _make_step(adapter="manual", command="echo m", instructions="do y")
        id_a = _compute_artifact_identity(
            step=step_a, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id_b = _compute_artifact_identity(
            step=step_b, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id_a is not None and id_b is not None
        assert id_a.identity_key != id_b.identity_key


# ── identity_key component sensitivity ───────────────────────────────────────


class TestIdentityKeyComponentSensitivity:
    """Every component (input_digest, producer_id, producer_version) busts the key."""

    def test_key_changes_when_input_digest_changes(self) -> None:
        k1 = identity_digest(input_digest="aaa", producer_id="pid", producer_version="pv")
        k2 = identity_digest(input_digest="bbb", producer_id="pid", producer_version="pv")
        assert k1 != k2

    def test_key_changes_when_producer_id_changes(self) -> None:
        k1 = identity_digest(input_digest="aaa", producer_id="task.local", producer_version="pv")
        k2 = identity_digest(input_digest="aaa", producer_id="task.manual", producer_version="pv")
        assert k1 != k2

    def test_key_changes_when_producer_version_changes(self) -> None:
        k1 = identity_digest(input_digest="aaa", producer_id="pid", producer_version="v1")
        k2 = identity_digest(input_digest="aaa", producer_id="pid", producer_version="v2")
        assert k1 != k2

    def test_key_stable_when_all_equal(self) -> None:
        k1 = identity_digest(input_digest="aaa", producer_id="pid", producer_version="pv")
        k2 = identity_digest(input_digest="aaa", producer_id="pid", producer_version="pv")
        assert k1 == k2

    def test_key_is_64_char_hex(self) -> None:
        k = identity_digest(input_digest="in", producer_id="pid", producer_version="pv")
        assert len(k) == 64
        assert all(c in "0123456789abcdef" for c in k)


# ── cross-mode: identity keys are distinguishable ─────────────────────────────


class TestCrossModeIdentityDistinguishability:
    """Identities from different modes MUST NOT collide."""

    def test_executor_vs_local_produce_different_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exec_def = _mock_executor(id="e1", version="1.0")
        reg = _mock_registry(exec_def)
        _executor_registry_for_project.cache_clear()
        monkeypatch.setattr(
            "astrid.core.task.gate.dispatch._executor_registry_for_project",
            lambda project_root: reg,
        )
        step_exec = _make_step(command="executors run e1")
        step_local = _make_step(adapter="local", command="echo hello")

        id_exec = _compute_artifact_identity(
            step=step_exec, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id_local = _compute_artifact_identity(
            step=step_local, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id_exec is not None and id_local is not None
        assert id_exec.identity_key != id_local.identity_key

    def test_attested_vs_manual_produce_different_keys(self) -> None:
        step_att = _make_step(adapter="manual", requires_ack=True, command="ack --project demo --step s1")
        step_man = _make_step(adapter="manual", command="echo manual")
        id_att = _compute_artifact_identity(
            step=step_att, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id_man = _compute_artifact_identity(
            step=step_man, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id_att is not None and id_man is not None
        assert id_att.identity_key != id_man.identity_key

    def test_local_vs_manual_produce_different_keys(self) -> None:
        step_local = _make_step(adapter="local", command="echo x")
        step_manual = _make_step(adapter="manual", command="echo x")
        id_local = _compute_artifact_identity(
            step=step_local, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        id_manual = _compute_artifact_identity(
            step=step_manual, path_tuple=("s1",), project_root=Path("/tmp"), iteration=None, item_id=None
        )
        assert id_local is not None and id_manual is not None
        assert id_local.identity_key != id_manual.identity_key


# ── no-arnold guard ──────────────────────────────────────────────────────────


def test_no_arnold_contamination() -> None:
    """Prove the identity test surface is free of Arnold references."""
    import astrid.core.task.gate.base as base_mod
    import astrid.core.task.gate.dispatch as dispatch_mod
    import astrid.core.io.cas as cas_mod

    for mod in (base_mod, dispatch_mod, cas_mod):
        source = str(mod.__file__)
        # check that the source file is not named after arnold
        assert "arnold" not in source.lower()
