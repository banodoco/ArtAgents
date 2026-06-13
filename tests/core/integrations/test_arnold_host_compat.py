from __future__ import annotations

import importlib
import sys
import types

import pytest


def _clear_host_modules() -> None:
    for name in (
        "astrid.core.integrations.arnold.host.builder",
        "astrid.core.integrations.arnold.host.compat",
        "astrid.core.integrations.arnold.host",
        "astrid.core.integrations.arnold",
    ):
        sys.modules.pop(name, None)


def _install_fake_pipeline(monkeypatch: pytest.MonkeyPatch, pipeline: types.ModuleType) -> None:
    fake_arnold = types.ModuleType("arnold")
    fake_arnold.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "arnold", fake_arnold)
    monkeypatch.setitem(sys.modules, "arnold.pipeline", pipeline)


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_host_modules()
    yield
    _clear_host_modules()


def test_host_package_import_stays_lazy_when_arnold_contract_is_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_host_modules()

    broken_pipeline = types.ModuleType("arnold.pipeline")
    _install_fake_pipeline(monkeypatch, broken_pipeline)

    host_pkg = importlib.import_module("astrid.core.integrations.arnold.host")

    assert host_pkg is not None
    assert "astrid.core.integrations.arnold.host.compat" not in sys.modules


def test_compat_reports_missing_symbols_and_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_host_modules()

    class CrossCutting:
        cost = 0

    class RuntimeEnvelope:
        artifact_root = ""
        resume_cursor = ""
        cross_cutting = CrossCutting()

    class StepContext:
        inputs = None

    class ContractResult:
        status = "ok"

    class Suspension:
        reason = "wait"

    class StepwiseDriver:
        def advance(self, envelope: object) -> object:
            return object()

        def checkpoint(self) -> object:
            return object()

        def resume(self, envelope: object) -> object:
            return object()

    pipeline = types.ModuleType("arnold.pipeline")
    pipeline.RuntimeEnvelope = RuntimeEnvelope
    pipeline.StepContext = StepContext
    pipeline.ContractResult = ContractResult
    pipeline.Suspension = Suspension
    pipeline.StepwiseDriver = StepwiseDriver
    pipeline.PipelineBuilder = type("PipelineBuilder", (), {})
    pipeline.Stage = type("Stage", (), {})
    pipeline.ParallelStage = type("ParallelStage", (), {})
    pipeline.Edge = type("Edge", (), {})
    pipeline.ExecutorHooks = type("ExecutorHooks", (), {})
    pipeline.StepInvocation = type("StepInvocation", (), {})
    pipeline.ContractStatus = type("ContractStatus", (), {})
    pipeline.PipelineVerdict = type("PipelineVerdict", (), {})
    pipeline.persist_resume_cursor = lambda *args, **kwargs: None

    _install_fake_pipeline(monkeypatch, pipeline)

    with pytest.raises(ImportError) as excinfo:
        importlib.import_module("astrid.core.integrations.arnold.host.compat")

    message = str(excinfo.value)
    assert "missing symbol arnold.pipeline.ResumeCursorRef" in message
    assert "missing symbol arnold.pipeline.AdvanceOutcome" in message
    assert "missing symbol arnold.pipeline.read_resume_cursor" in message
    assert "RuntimeEnvelope missing field(s): run_id" in message
    assert "RuntimeEnvelope.cross_cutting missing field(s): lineage" in message
    assert "StepContext missing field(s): hook_extensions" in message
    assert "ContractResult missing field(s): suspension" in message
    assert "Suspension missing field(s): resume_input_schema" in message
    assert "StepwiseDriver.checkpoint signature starts with ('self',)" in message
    assert "StepwiseDriver.resume signature starts with ('self', 'envelope')" in message


def test_compat_exports_validated_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_host_modules()

    class CrossCutting:
        cost = 0
        lineage = None

    class RuntimeEnvelope:
        run_id = "run-1"
        artifact_root = "/tmp/run-1"
        resume_cursor = "cursor.json"
        cross_cutting = CrossCutting()

    class StepContext:
        inputs = None
        hook_extensions = None

    class ContractResult:
        suspension = None

    class Suspension:
        resume_input_schema = None

    class StepwiseDriver:
        def advance(self, envelope: object) -> object:
            return object()

        def checkpoint(self, envelope: object) -> object:
            return object()

        def resume(self, envelope: object, cursor: object) -> object:
            return object()

    pipeline = types.ModuleType("arnold.pipeline")
    required_symbols = {
        "RuntimeEnvelope": RuntimeEnvelope,
        "ResumeCursorRef": type("ResumeCursorRef", (), {}),
        "AdvanceOutcome": type("AdvanceOutcome", (), {}),
        "CheckpointOutcome": type("CheckpointOutcome", (), {}),
        "StepwiseDriver": StepwiseDriver,
        "PipelineBuilder": type("PipelineBuilder", (), {}),
        "Stage": type("Stage", (), {}),
        "ParallelStage": type("ParallelStage", (), {}),
        "Edge": type("Edge", (), {}),
        "Suspension": Suspension,
        "StepContext": StepContext,
        "ExecutorHooks": type("ExecutorHooks", (), {}),
        "StepInvocation": type("StepInvocation", (), {}),
        "ContractResult": ContractResult,
        "ContractStatus": type("ContractStatus", (), {}),
        "PipelineVerdict": type("PipelineVerdict", (), {}),
        "persist_resume_cursor": lambda *args, **kwargs: None,
        "read_resume_cursor": lambda *args, **kwargs: None,
        "EvidenceArtifactRef": type("EvidenceArtifactRef", (), {}),
        "Provenance": type("Provenance", (), {}),
        "StepResult": type("StepResult", (), {}),
        "StepInvocationAdapter": type("StepInvocationAdapter", (), {}),
        "StepInvocationAdapterRegistry": type("StepInvocationAdapterRegistry", (), {}),
        "ContentValidatorRegistry": type("ContentValidatorRegistry", (), {}),
        "no_op_content_validator": lambda *args, **kwargs: None,
    }
    for name, value in required_symbols.items():
        setattr(pipeline, name, value)

    _install_fake_pipeline(monkeypatch, pipeline)

    compat_module = importlib.import_module("astrid.core.integrations.arnold.host.compat")

    assert compat_module.compat.RuntimeEnvelope is RuntimeEnvelope
    assert compat_module.compat.StepwiseDriver is StepwiseDriver
    assert compat_module.read_resume_cursor is required_symbols["read_resume_cursor"]


# ── Builder helpers (T2) ───────────────────────────────────────────────────────


def _build_minimal_valid_pipeline_module(**extra_attrs: object) -> types.ModuleType:
    """Return a fake ``arnold.pipeline`` module with just the symbols the
    compat module requires, plus any *extra_attrs*.

    Deliberately omits ``Port``, ``PortRef``, and ``Pipeline`` to prove the
    builder/compiler does not require them.
    """

    class CrossCutting:
        cost = 0
        lineage = None

    class RuntimeEnvelope:
        run_id = "run-1"
        artifact_root = "/tmp/run-1"
        resume_cursor = "cursor.json"
        cross_cutting = CrossCutting()

    class StepContext:
        inputs = None
        hook_extensions = None

    class ContractResult:
        suspension = None

    class Suspension:
        resume_input_schema = None

    class StepwiseDriver:
        def advance(self, envelope: object) -> object:
            return object()

        def checkpoint(self, envelope: object) -> object:
            return object()

        def resume(self, envelope: object, cursor: object) -> object:
            return object()

    # ── Duck-typed constructible types ────────────────────────────────────
    # These accept **kwargs so the builder's duck-typing can construct them.
    class _FakeConstructible:
        def __init__(self, **kwargs: object) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

    FakeStage = type("Stage", (_FakeConstructible,), {})
    FakeParallelStage = type("ParallelStage", (_FakeConstructible,), {})
    FakeEdge = type("Edge", (_FakeConstructible,), {})

    pipeline = types.ModuleType("arnold.pipeline")
    pipeline.RuntimeEnvelope = RuntimeEnvelope
    pipeline.ResumeCursorRef = type("ResumeCursorRef", (), {})
    pipeline.AdvanceOutcome = type("AdvanceOutcome", (), {})
    pipeline.CheckpointOutcome = type("CheckpointOutcome", (), {})
    pipeline.StepwiseDriver = StepwiseDriver
    pipeline.PipelineBuilder = type("PipelineBuilder", (), {})
    pipeline.Stage = FakeStage
    pipeline.ParallelStage = FakeParallelStage
    pipeline.Edge = FakeEdge
    pipeline.Suspension = Suspension
    pipeline.StepContext = StepContext
    pipeline.ExecutorHooks = type("ExecutorHooks", (), {})
    pipeline.StepInvocation = type("StepInvocation", (), {})
    pipeline.ContractResult = ContractResult
    pipeline.ContractStatus = type("ContractStatus", (), {})
    pipeline.PipelineVerdict = type("PipelineVerdict", (), {})
    pipeline.persist_resume_cursor = lambda *args, **kwargs: None
    pipeline.read_resume_cursor = lambda *args, **kwargs: None
    pipeline.EvidenceArtifactRef = type("EvidenceArtifactRef", (), {})
    pipeline.Provenance = type("Provenance", (), {})
    pipeline.StepResult = type("StepResult", (), {})
    pipeline.StepInvocationAdapter = type("StepInvocationAdapter", (), {})
    pipeline.StepInvocationAdapterRegistry = type("StepInvocationAdapterRegistry", (), {})
    pipeline.ContentValidatorRegistry = type("ContentValidatorRegistry", (), {})
    pipeline.no_op_content_validator = lambda *args, **kwargs: None

    for name, value in extra_attrs.items():
        setattr(pipeline, name, value)

    return pipeline


def _install_arnold_modules(
    monkeypatch: pytest.MonkeyPatch, pipeline: types.ModuleType
) -> None:
    """Inject *pipeline* as ``arnold.pipeline`` in ``sys.modules``."""
    fake_arnold = types.ModuleType("arnold")
    fake_arnold.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "arnold", fake_arnold)
    monkeypatch.setitem(sys.modules, "arnold.pipeline", pipeline)


def _import_builder() -> Any:
    """Import the builder module and return it."""
    return importlib.import_module(
        "astrid.core.integrations.arnold.host.builder"
    )


def _assert_no_port_pipeline_portref(pipeline_module: types.ModuleType) -> None:
    """Confirm *pipeline_module* does not expose Port, PortRef, or Pipeline."""
    for forbidden in ("Port", "PortRef", "Pipeline"):
        assert not hasattr(pipeline_module, forbidden), (
            f"fake pipeline module must not expose {forbidden}"
        )


class TestBuilderCompatibility:
    """Focused compat/builder tests that use fake Arnold surfaces omitting
    ``Port``, ``PortRef``, and ``Pipeline``."""

    def test_builder_with_build_finalizes_via_build_method(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A builder with a ``build()`` method returns its result from
        ``builder_finalize``."""
        _clear_host_modules()

        BuiltPipeline = type("BuiltPipeline", (), {})
        build_calls: list[None] = []

        class BuilderWithBuild:
            def __init__(self) -> None:
                self.stages: list[Any] = []
                self.edges: list[Any] = []

            def add_stage(self, stage: Any) -> None:
                self.stages.append(stage)

            def add_edge(self, edge: Any) -> None:
                self.edges.append(edge)

            def set_entry_stage(self, stage_id: str) -> None:
                self._entry_stage_id = stage_id

            def build(self) -> Any:
                build_calls.append(None)
                return BuiltPipeline()

        pipeline = _build_minimal_valid_pipeline_module(
            PipelineBuilder=BuilderWithBuild,
        )
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        builder = pipeline.PipelineBuilder()
        stage = builder_mod.build_stage(
            pipeline.Stage, stage_id="s1", label="Step 1"
        )
        builder_mod.builder_add_stage(builder, stage)
        builder_mod.builder_set_entry_stage(builder, "s1")

        result = builder_mod.builder_finalize(builder)
        assert isinstance(result, BuiltPipeline)
        assert len(build_calls) == 1

    def test_builder_without_build_finalizes_as_itself(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the builder has no ``build()`` method, ``builder_finalize``
        returns the builder itself as the opaque pipeline."""
        _clear_host_modules()

        class BuilderWithoutBuild:
            def __init__(self) -> None:
                self.stages: list[Any] = []
                self.edges: list[Any] = []

            def add_stage(self, stage: Any) -> None:
                self.stages.append(stage)

            def add_edge(self, edge: Any) -> None:
                self.edges.append(edge)

            def set_entry_stage(self, stage_id: str) -> None:
                self._entry_stage_id = stage_id

        pipeline = _build_minimal_valid_pipeline_module(
            PipelineBuilder=BuilderWithoutBuild,
        )
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        builder = pipeline.PipelineBuilder()
        stage = builder_mod.build_stage(
            pipeline.Stage, stage_id="s1", label="Step 1"
        )
        builder_mod.builder_add_stage(builder, stage)

        result = builder_mod.builder_finalize(builder)
        assert result is builder

    def test_stage_and_edge_insertion_and_entry_stage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end: add stages, edges, set entry, finalize — all through
        duck-typed helpers with a builder that has ``build()``."""
        _clear_host_modules()

        BuiltPipeline = type("BuiltPipeline", (), {})

        class RecordingBuilder:
            def __init__(self) -> None:
                self.stages: list[Any] = []
                self.edges: list[Any] = []

            def add_stage(self, stage: Any) -> None:
                self.stages.append(stage)

            def add_edge(self, edge: Any) -> None:
                self.edges.append(edge)

            def set_entry_stage(self, stage_id: str) -> None:
                self._entry_stage_id = stage_id

            def build(self) -> Any:
                return BuiltPipeline()

        pipeline = _build_minimal_valid_pipeline_module(
            PipelineBuilder=RecordingBuilder,
        )
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        builder = pipeline.PipelineBuilder()
        s1 = builder_mod.build_stage(
            pipeline.Stage, stage_id="entry", label="Entry"
        )
        s2 = builder_mod.build_stage(
            pipeline.Stage, stage_id="halt", label="Halt"
        )
        builder_mod.builder_add_stage(builder, s1)
        builder_mod.builder_add_stage(builder, s2)

        edge = builder_mod.build_edge(
            pipeline.Edge, source="entry", target="halt", label="done"
        )
        builder_mod.builder_add_edge(builder, edge)

        builder_mod.builder_set_entry_stage(builder, "entry")

        result = builder_mod.builder_finalize(builder)
        assert isinstance(result, BuiltPipeline)
        assert len(builder.stages) == 2
        assert len(builder.edges) == 1
        assert builder._entry_stage_id == "entry"

    def test_builder_stage_list_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the builder has no ``add_stage``/``add_edge`` methods but
        exposes ``stages`` and ``edges`` list attributes, the helpers fall
        back to appending."""
        _clear_host_modules()

        class ListBasedBuilder:
            def __init__(self) -> None:
                self.stages: list[Any] = []
                self.edges: list[Any] = []

            def build(self) -> Any:
                return self

        pipeline = _build_minimal_valid_pipeline_module(
            PipelineBuilder=ListBasedBuilder,
        )
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        builder = pipeline.PipelineBuilder()
        stage = builder_mod.build_stage(
            pipeline.Stage, stage_id="s1", label="Step"
        )
        builder_mod.builder_add_stage(builder, stage)
        edge = builder_mod.build_edge(
            pipeline.Edge, source="s1", target="s2", label="next"
        )
        builder_mod.builder_add_edge(builder, edge)

        assert len(builder.stages) == 1
        assert len(builder.edges) == 1

    def test_entry_stage_attribute_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the builder has no entry-stage setter method but exposes an
        ``entry_stage_id`` attribute, the helper sets it directly."""
        _clear_host_modules()

        class AttrBasedBuilder:
            def __init__(self) -> None:
                self.stages: list[Any] = []
                self.entry_stage_id: str | None = None

            def add_stage(self, stage: Any) -> None:
                self.stages.append(stage)

            def build(self) -> Any:
                return self

        pipeline = _build_minimal_valid_pipeline_module(
            PipelineBuilder=AttrBasedBuilder,
        )
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        builder = pipeline.PipelineBuilder()
        stage = builder_mod.build_stage(
            pipeline.Stage, stage_id="main", label="Main"
        )
        builder_mod.builder_add_stage(builder, stage)
        builder_mod.builder_set_entry_stage(builder, "main")

        assert builder.entry_stage_id == "main"

    def test_no_port_pipeline_portref_symbols_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prove that the compat and builder modules never require
        ``Port``, ``PortRef``, or ``Pipeline`` to exist on the Arnold
        pipeline module."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        compat_mod = importlib.import_module(
            "astrid.core.integrations.arnold.host.compat"
        )
        assert not hasattr(compat_mod.compat, "Port")
        assert not hasattr(compat_mod.compat, "PortRef")
        assert not hasattr(compat_mod.compat, "Pipeline")

        builder_mod = _import_builder()
        stage = builder_mod.build_stage(
            pipeline.Stage, stage_id="x", label="X"
        )
        assert stage is not None
        # No import errors — Port/PortRef/Pipeline were never needed.

    def test_parallel_stage_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``build_parallel_stage`` constructs a ParallelStage with
        sub-stages through duck-typing."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        sub_a = builder_mod.build_stage(
            pipeline.Stage, stage_id="a", label="A"
        )
        sub_b = builder_mod.build_stage(
            pipeline.Stage, stage_id="b", label="B"
        )
        parallel = builder_mod.build_parallel_stage(
            pipeline.ParallelStage,
            stage_id="fan",
            label="Fan-out",
            sub_stages=[sub_a, sub_b],
        )
        assert parallel is not None
        assert isinstance(parallel, pipeline.ParallelStage)
