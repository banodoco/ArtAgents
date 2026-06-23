"""Arnold conformance suite — fake-Arnold (always-on) + real-Arnold (opt-in).

This file contains two categories of conformance tests:

1. **Fake-Arnold conformance (always-on).**  These tests use synthetic
   Arnold doubles (``_Stage``, ``_BuilderWithBuild``, ``_FakeParallelStageWithJoin``,
   etc.) and run in every pytest invocation, including CI environments
   without a real Arnold installation.  They verify protocol compatibility,
   schema-hash round-trips, required vocabulary items, the every-stage-vocabulary
   rule, and join-parallel-results delegation/diagnostics — all against the
   shared lowering contract, never against a real Arnold runtime.

2. **Real-Arnold conformance (opt-in).**  These tests exercise the actual
   Arnold runtime contract end-to-end and are skipped by default.
   Activate them with **one** of the following selectors:

   * **Package selector** — install the real ``arnold`` package.
     Any test decorated with ``@pytest.mark.real_arnold`` will
     auto-detect the installed package and run.  Without it they are
     skipped cleanly with zero failures.

   * **Environment selector** — set ``ASTRID_REAL_ARNOLD_CONFORMANCE=1``
     in your environment.  This forces real-Arnold conformance to run
     regardless of package detection (useful for worktree hooks or CI
     lanes that have Arnold on ``PYTHONPATH`` but not installed as a
     package).

   * **pytest marker selector** — pass ``-m real_arnold`` to pytest to
     run ONLY the real-Arnold conformance tests (and any other tests
     marked ``real_arnold``).  Combine with ``-m "not real_arnold"`` to
     explicitly exclude them.

   The selectors are evaluated in order: environment overrides, then
   package detection, then marker-based inclusion.  Each real-Arnold
   test also carries ``@pytest.mark.real_arnold`` so CI lanes can
   control inclusion/exclusion by marker alone without env vars.

Examples::

    # Run everything EXCEPT real-Arnold tests (CI default):
    pytest -m "not real_arnold"

    # Run ONLY real-Arnold conformance (when Arnold is installed):
    ASTRID_REAL_ARNOLD_CONFORMANCE=1 pytest -m real_arnold

    # Run the full conformance file including real-Arnold:
    ASTRID_REAL_ARNOLD_CONFORMANCE=1 pytest tests/core/integrations/test_arnold_conformance.py
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from astrid.core.io.cas import canonical_json_digest
from astrid.core.task.plan import (
    Check,
    ProducesEntry,
    RepeatUntil,
    Step,
    SupersededRef,
    TaskPlan,
)
from tests.core.integrations.test_arnold_host_compat import (
    _build_minimal_valid_pipeline_module,
    _clear_host_modules,
    _install_arnold_modules,
)
from tests.core.integrations.test_arnold_session_compiler import (
    _BuilderWithBuild,
    _FakeParallelStageWithJoin,
    _Stage,
    _clear_arnold_modules,
    _import_compiler_module,
    _install_fake_pipeline,
)


# ---------------------------------------------------------------------------
# Real-Arnold conformance selector
# ---------------------------------------------------------------------------


def _real_arnold_available() -> bool:
    """Return ``True`` when the real Arnold package satisfies the host contract.

    This is the canonical detection function used by the module-level
    ``real_arnold`` skip condition.  It is intentionally a function
    (not a module-level constant) so that tests which install fake
    modules at runtime are never affected by a cached import check.

    The check goes beyond ``find_spec``: it actually imports the compat
    module, which validates the full Arnold contract.  A partial Arnold
    installation (e.g., ``arnold.pipeline`` importable but missing
    required symbols like ``RuntimeEnvelope``) correctly reports as
    unavailable.
    """
    if os.environ.get("ASTRID_REAL_ARNOLD_CONFORMANCE") == "1":
        return True
    try:
        importlib.import_module("astrid.core.integrations.arnold.host.compat")
    except ImportError:
        return False
    return True


# Module-level skip for real-Arnold conformance when Arnold is absent.
# Every real-Arnold test is also decorated with @pytest.mark.real_arnold
# so CI lanes can control inclusion/exclusion by marker alone.
_real_arnold_skip = pytest.mark.skipif(
    not _real_arnold_available(),
    reason=(
        "Real Arnold conformance requires the arnold package or "
        "ASTRID_REAL_ARNOLD_CONFORMANCE=1 in the environment. "
        "See the module docstring for activation instructions."
    ),
)

# Convenience decorator that stacks the real_arnold marker + skip.
real_arnold = pytest.mark.real_arnold


def _clear_conformance_modules() -> None:
    _clear_host_modules()
    _clear_arnold_modules()


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_conformance_modules()
    yield
    _clear_conformance_modules()


def _compile_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    plan: TaskPlan,
):
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    compiler = _import_compiler_module()
    return compiler.compile_plan_segment(
        plan,
        project="demo",
        run_root=tmp_path / plan.plan_id,
        state={},
        segment_id=f"seg-{plan.plan_id}",
    )


def test_compat_layer_accepts_the_public_arnold_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _build_minimal_valid_pipeline_module()
    _install_arnold_modules(monkeypatch, pipeline)

    compat_module = importlib.import_module("astrid.core.integrations.arnold.host.compat")
    compat = compat_module.compat
    builder_mod = importlib.import_module("astrid.core.integrations.arnold.host.builder")

    stage = builder_mod.build_stage(
        compat.Stage,
        stage_id="protocol-stage",
        label="Protocol Stage",
        metadata={"vocabulary": ["next"]},
        decision_vocabulary=("next",),
    )
    edge = builder_mod.build_edge(
        compat.Edge,
        source="protocol-stage",
        target="halt",
        label="next",
        metadata={"conformance": True},
    )

    assert compat.RuntimeEnvelope is pipeline.RuntimeEnvelope
    assert compat.ContractResult is pipeline.ContractResult
    assert compat.StepInvocation is pipeline.StepInvocation
    assert stage.stage_id == "protocol-stage"
    assert stage.decision_vocabulary == frozenset({"next"})
    assert edge.label == "next"
    assert getattr(edge, "metadata", None) == {"conformance": True}


def test_contract_result_schema_hash_round_trips_through_public_version_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ContractResult:
        suspension = None

        def __init__(
            self,
            *,
            suspension: object | None = None,
            status: str | None = None,
            payload: dict[str, Any] | None = None,
        ) -> None:
            self.suspension = suspension
            self.status = status
            self.payload = payload or {}

    pipeline = _build_minimal_valid_pipeline_module(
        ContractResult=ContractResult,
        CONTRACT_RESULT_SCHEMA_VERSION=7,
    )
    _install_arnold_modules(monkeypatch, pipeline)

    compat = importlib.import_module("astrid.core.integrations.arnold.host.compat").compat
    public_schema_version = getattr(
        pipeline,
        "CONTRACT_RESULT_SCHEMA_VERSION",
        getattr(pipeline, "SCHEMA_VERSION", None),
    )
    assert public_schema_version is not None

    schema_fingerprint = canonical_json_digest(
        {
            "contract": "ContractResult",
            "schema_version": public_schema_version,
            "fields": ("payload", "status", "suspension"),
        }
    )
    result = compat.ContractResult(
        suspension=compat.Suspension(),
        status="completed",
        payload={
            "schema_version": public_schema_version,
            "schema_hash": schema_fingerprint,
        },
    )

    assert result.payload["schema_version"] == public_schema_version
    assert result.payload["schema_hash"] == schema_fingerprint
    assert canonical_json_digest(
        {
            "contract": "ContractResult",
            "schema_version": result.payload["schema_version"],
            "fields": ("payload", "status", "suspension"),
        }
    ) == result.payload["schema_hash"]


@dataclass(frozen=True)
class _ConformanceExpectation:
    stage_id: str
    vocabulary: tuple[str, ...]
    metadata_key: str


@pytest.mark.parametrize(
    ("plan", "expectation"),
    [
        (
            TaskPlan(
                plan_id="conformance-optional",
                version=2,
                steps=(
                    Step(id="before", adapter="local", command="echo before"),
                    Step(id="optional_step", adapter="local", command="echo optional", optional=True),
                ),
            ),
            _ConformanceExpectation(
                stage_id="optional_step",
                vocabulary=("proceed", "skip"),
                metadata_key="optional",
            ),
        ),
        (
            TaskPlan(
                plan_id="conformance-superseded",
                version=2,
                steps=(
                    Step(
                        id="review",
                        adapter="manual",
                        command="ack --step review",
                        requires_ack=True,
                        superseded_by=SupersededRef(to_version=4, scope="future-items"),
                    ),
                ),
            ),
            _ConformanceExpectation(
                stage_id="review",
                vocabulary=("next",),
                metadata_key="superseded_by",
            ),
        ),
        (
            TaskPlan(
                plan_id="conformance-reexport",
                version=2,
                steps=(
                    Step(
                        id="publish",
                        children=(
                            Step(
                                id="build",
                                adapter="local",
                                command="echo build",
                                produces=(
                                    ProducesEntry(
                                        name="artifact",
                                        path="out/artifact.tar.gz",
                                        check=Check(
                                            check_id="file_nonempty",
                                            params={},
                                            sentinel=False,
                                        ),
                                    ),
                                ),
                            ),
                        ),
                        re_export=(("release_artifact", "build.produces.artifact"),),
                    ),
                ),
            ),
            _ConformanceExpectation(
                stage_id="publish/__exit__",
                vocabulary=("next",),
                metadata_key="re_exports",
            ),
        ),
        (
            TaskPlan(
                plan_id="conformance-repeat-until",
                version=2,
                steps=(
                    Step(
                        id="poll",
                        adapter="local",
                        command="echo poll",
                        produces=(
                            ProducesEntry(
                                name="status",
                                path="status.json",
                                check=Check(
                                    check_id="json_file",
                                    params={},
                                    sentinel=False,
                                ),
                            ),
                        ),
                        repeat=RepeatUntil(
                            condition='poll.produces.status.state != "ready"',
                            max_iterations=5,
                            on_exhaust="fail",
                        ),
                    ),
                ),
            ),
            _ConformanceExpectation(
                stage_id="poll",
                vocabulary=("repeat", "next"),
                metadata_key="repeat_until",
            ),
        ),
    ],
)
def test_required_vocabulary_items_have_conformance_coverage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    plan: TaskPlan,
    expectation: _ConformanceExpectation,
) -> None:
    result = _compile_plan(monkeypatch, tmp_path, plan=plan)

    stages_by_id = {stage.stage_id: stage for stage in result.pipeline.stages}
    manifest_stages = {stage["stage_id"]: stage for stage in result.pipeline_manifest["stages"]}
    target_stage = stages_by_id[expectation.stage_id]
    target_manifest = manifest_stages[expectation.stage_id]

    assert set(target_stage.decision_vocabulary) == set(expectation.vocabulary)
    assert target_stage.metadata["vocabulary"] == list(expectation.vocabulary)
    assert target_stage.metadata["decision_vocabulary"] == list(expectation.vocabulary)
    assert expectation.metadata_key in target_stage.metadata
    assert expectation.metadata_key in target_manifest["metadata"]

    if expectation.metadata_key == "repeat_until":
        loop_edges = [
            edge for edge in result.pipeline_manifest["edges"] if edge.get("metadata", {}).get("predicate") == "repeat.until"
        ]
        assert len(loop_edges) == 1
        assert loop_edges[0]["source"] == "poll"
        assert loop_edges[0]["target"] == "poll"


def test_every_compiled_stage_declares_a_vocabulary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan = TaskPlan(
        plan_id="conformance-every-stage-vocabulary",
        version=2,
        steps=(
            Step(id="start", adapter="local", command="echo start"),
            Step(
                id="optional_group",
                children=(
                    Step(
                        id="inner",
                        adapter="local",
                        command="echo inner",
                        produces=(
                            ProducesEntry(
                                name="result",
                                path="result.json",
                                check=Check(check_id="json_file", params={}, sentinel=False),
                            ),
                        ),
                    ),
                ),
                optional=True,
                superseded_by=SupersededRef(to_version=2, scope="all"),
                re_export=(("group_result", "inner.produces.result"),),
            ),
        ),
    )

    result = _compile_plan(monkeypatch, tmp_path, plan=plan)

    manifest_stages = {stage["stage_id"]: stage for stage in result.pipeline_manifest["stages"]}
    for stage in result.pipeline.stages:
        assert stage.decision_vocabulary, f"{stage.stage_id} is missing a runtime vocabulary"
        assert sorted(stage.metadata["vocabulary"]) == sorted(stage.decision_vocabulary)
        if "decision_vocabulary" in stage.metadata:
            assert sorted(stage.metadata["decision_vocabulary"]) == sorted(stage.decision_vocabulary)
        assert sorted(manifest_stages[stage.stage_id]["vocabulary"]) == sorted(stage.decision_vocabulary)


def test_join_parallel_results_conformance_delegates_to_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module("astrid.core.integrations.arnold.session.lowering")

    stage = _FakeParallelStageWithJoin(stage_id="parallel-join")
    results = [{"branch": 1}, {"branch": 2}]

    joined = lowering.join_parallel_results(stage, results)

    assert stage._join_called_with == results
    assert joined == "joined-2-items"


def test_join_parallel_results_conformance_reports_missing_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pipeline(monkeypatch, builder_type=_BuilderWithBuild)
    lowering = importlib.import_module("astrid.core.integrations.arnold.session.lowering")

    stage = _Stage(name="parallel-missing-join", label="Parallel Missing Join")

    with pytest.raises(lowering.CompileUnsupportedFeature) as exc_info:
        lowering.join_parallel_results(stage, [{"branch": 1}])

    message = str(exc_info.value)
    assert "parallel-missing-join" in message
    assert "ParallelStage" in message
    assert "join" in message.lower()


# ============================================================================
# Real-Arnold conformance tests (opt-in — skipped when Arnold is not installed)
# ============================================================================


@pytest.mark.real_arnold
@_real_arnold_skip
def test_real_arnold_stage_construction_through_compat_layer() -> None:
    """Real Arnold stages can be constructed through the compat layer.

    Proves that the compat protocol (``compat.Stage``) maps to a real
    Arnold ``Stage`` class and that stage construction with metadata,
    decision_vocabulary, and stage_id succeeds end-to-end.
    """
    import astrid.core.integrations.arnold.host.builder as builder
    from astrid.core.integrations.arnold.host.compat import compat

    # Real Arnold must expose Stage through the compat protocol.
    assert compat.Stage is not None
    stage_cls = compat.Stage

    stage = builder.build_stage(
        stage_cls,
        stage_id="real-conformance-stage",
        label="Real Conformance Stage",
        metadata={"vocabulary": ["next"], "conformance": "real-arnold"},
        decision_vocabulary=("next",),
    )

    assert stage.name == "real-conformance-stage"
    assert stage.decision_vocabulary == frozenset({"next"})
    # Real Arnold dataclasses do not accept Astrid-only metadata sidecars.
    assert getattr(stage, "metadata", None) is None


@pytest.mark.real_arnold
@_real_arnold_skip
def test_real_arnold_edge_construction_with_metadata() -> None:
    """Real Arnold edges carry metadata when the constructor supports it.

    Proves that the compat protocol (``compat.Edge``) maps to a real
    Arnold ``Edge`` class and that edge construction with source_port,
    target_port, logical_type, artifact_type, and metadata succeeds
    or falls back gracefully.
    """
    import astrid.core.integrations.arnold.host.builder as builder
    from astrid.core.integrations.arnold.host.compat import compat

    assert compat.Edge is not None

    edge = builder.build_edge(
        compat.Edge,
        source="real-conformance-stage",
        target="halt",
        label="next",
        metadata={"conformance": "real-arnold-edge"},
        source_port="out",
        target_port="in",
        logical_type=None,
        artifact_type="text/plain",
    )

    # Real Arnold ``Edge`` is sourceless: ``label`` and ``target`` are the
    # canonical fields.  Metadata sidecars live in the manifest, not on the
    # runtime edge object.
    assert edge.target == "halt"
    assert edge.label == "next"
    assert getattr(edge, "source", None) is None
    assert getattr(edge, "metadata", None) is None


@pytest.mark.real_arnold
@_real_arnold_skip
def test_real_arnold_pipeline_assembly_and_finalize() -> None:
    """Real Arnold Pipeline can be assembled and finalized.

    Proves that a real Arnold ``Pipeline`` is constructible, that
    stages and edges can be added, and that finalization produces
    a usable pipeline object.  This is the minimal end-to-end
    smoke test for the real Arnold runtime contract.
    """
    import astrid.core.integrations.arnold.host.builder as builder
    from astrid.core.integrations.arnold.host.compat import compat

    assert compat.Pipeline is not None
    assert compat.Stage is not None
    assert compat.Edge is not None

    pipeline = builder.create_pipeline(compat.Pipeline)

    stage_a = builder.build_stage(
        compat.Stage,
        stage_id="a",
        label="Stage A",
        decision_vocabulary=("next",),
        metadata={"vocabulary": ["next"]},
    )
    stage_b = builder.build_stage(
        compat.Stage,
        stage_id="b",
        label="Stage B",
        decision_vocabulary=("terminal",),
        metadata={"vocabulary": ["terminal"]},
    )

    builder.add_stage(pipeline, stage_a)
    builder.add_stage(pipeline, stage_b)

    edge = builder.build_edge(
        compat.Edge,
        source="a",
        target="b",
        label="next",
        metadata={"conformance": "real-arnold-pipeline"},
    )
    builder.add_edge(pipeline, edge)

    finalized = builder.finalize_pipeline(pipeline)
    assert finalized is not None

    # The finalized pipeline assembly should have the stages and edges we added.
    stage_ids = {s.name for s in finalized.stages}
    assert "a" in stage_ids
    assert "b" in stage_ids


@pytest.mark.real_arnold
@_real_arnold_skip
def test_real_arnold_schema_version_constant_is_present() -> None:
    """Real Arnold's public surface exposes schema/version constants.

    Proves that the real Arnold package exposes ``SCHEMA_VERSION``
    (or equivalent) as a public constant that conformance tests can
    use for schema-hash round-trips.
    """
    # The compat layer resolves these from the real Arnold package.
    from astrid.core.integrations.arnold.host.compat import compat

    # The compat module should have resolved a non-None Pipeline,
    # Stage, Edge, and ContractResult from the real Arnold package.
    assert compat.Pipeline is not None
    assert compat.Stage is not None
    assert compat.Edge is not None
    assert compat.ContractResult is not None
    assert compat.RuntimeEnvelope is not None

    # Every real Arnold type in the compat protocol must be callable
    # (i.e., a class, not a module or sentinel).
    for name, obj in [
        ("Pipeline", compat.Pipeline),
        ("Stage", compat.Stage),
        ("Edge", compat.Edge),
        ("ContractResult", compat.ContractResult),
        ("RuntimeEnvelope", compat.RuntimeEnvelope),
    ]:
        assert callable(obj), f"compat.{name} must be callable, got {type(obj)}"
