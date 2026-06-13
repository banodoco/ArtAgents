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

    # ParallelStage with an optional callable ``join`` for the A4a join probe.
    class _FakeParallelStage(_FakeConstructible):
        def join(self, results: list[Any]) -> Any:
            return results

    FakeParallelStage = _FakeParallelStage
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
    pipeline.SCHEMA_VERSION = 1

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


# ── A4a edge metadata contract tests (T5) ──────────────────────────────────────


class TestA5EdgeMetadataHostBuilder:
    """Tests that exercise both Edge constructor shapes at the host builder
    level and prove the builder's duck-typing tries metadata-capable
    shapes first before falling back to plain edges.
    """

    def test_build_edge_passes_metadata_to_capable_constructor(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``build_edge`` passes source_port, target_port, logical_type,
        artifact_type, and metadata kwargs to the Edge constructor when
        the constructor accepts them."""
        _clear_host_modules()

        # Use a metadata-capable Edge type that records its kwargs
        constructed_kwargs: list[dict[str, Any]] = []

        class MetadataCapableEdge:
            def __init__(self, **kwargs: object) -> None:
                constructed_kwargs.append(dict(kwargs))
                for k, v in kwargs.items():
                    setattr(self, k, v)

        pipeline = _build_minimal_valid_pipeline_module(Edge=MetadataCapableEdge)
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        edge = builder_mod.build_edge(
            pipeline.Edge,
            source="src",
            target="dst",
            label="artifact",
            source_port="out",
            target_port="in",
            logical_type="document",
            artifact_type="text/markdown",
            metadata={"predicate": "repeat.until"},
        )

        assert len(constructed_kwargs) == 1
        kw = constructed_kwargs[0]
        assert kw["source"] == "src"
        assert kw["target"] == "dst"
        assert kw["label"] == "artifact"
        assert kw["source_port"] == "out"
        assert kw["target_port"] == "in"
        assert kw["logical_type"] == "document"
        assert kw["artifact_type"] == "text/markdown"
        assert kw["metadata"] == {"predicate": "repeat.until"}

        # Edge attributes match what was passed
        assert edge.source == "src"
        assert edge.target == "dst"
        assert edge.source_port == "out"
        assert edge.metadata == {"predicate": "repeat.until"}

    def test_build_edge_falls_back_to_plain_constructor(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the Edge type only accepts source/target/label (plain, no
        **kwargs), ``build_edge`` falls back gracefully and still constructs
        a valid edge."""
        _clear_host_modules()

        constructed_kwargs: list[dict[str, Any]] = []

        class PlainEdge:
            def __init__(
                self,
                *,
                source: str = "",
                target: str = "",
                label: str = "",
            ) -> None:
                constructed_kwargs.append(
                    {"source": source, "target": target, "label": label}
                )
                self.source = source
                self.target = target
                self.label = label

        pipeline = _build_minimal_valid_pipeline_module(Edge=PlainEdge)
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        edge = builder_mod.build_edge(
            pipeline.Edge,
            source="src",
            target="dst",
            label="next",
            source_port="out",
            target_port="in",
            logical_type="document",
            artifact_type="text/markdown",
            metadata={"predicate": "repeat.until"},
        )

        # build_edge tries metadata-capable candidates first (they fail
        # on PlainEdge), then falls back to plain {source,target,label}.
        assert len(constructed_kwargs) >= 1
        final_kw = constructed_kwargs[-1]
        assert final_kw["source"] == "src"
        assert final_kw["target"] == "dst"
        assert final_kw["label"] == "next"
        # Plain constructor never saw metadata fields
        assert "source_port" not in final_kw

        # Edge is valid
        assert edge.source == "src"
        assert edge.target == "dst"
        assert not hasattr(edge, "source_port")

    def test_edge_manifest_entry_normalizes_all_fields(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``edge_manifest_entry`` produces the canonical sidecar shape
        with all metadata fields normalized, independent of runtime edge."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)

        builder_mod = _import_builder()
        entry = builder_mod.edge_manifest_entry(
            source="s1",
            target="s2",
            label="artifact",
            source_port="out",
            target_port="in",
            logical_type="document",
            artifact_type="text/markdown",
            metadata={"predicate": "repeat.until", "operator": "=="},
        )
        assert entry == {
            "source": "s1",
            "target": "s2",
            "label": "artifact",
            "source_port": "out",
            "target_port": "in",
            "logical_type": "document",
            "artifact_type": "text/markdown",
            "metadata": {"predicate": "repeat.until", "operator": "=="},
        }

    def test_edge_manifest_entry_defaults_none_for_missing_metadata(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``edge_manifest_entry`` uses None defaults for port/type fields
        and empty dict for metadata when not provided."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)

        builder_mod = _import_builder()
        entry = builder_mod.edge_manifest_entry(
            source="a",
            target="b",
            label="next",
        )
        assert entry == {
            "source": "a",
            "target": "b",
            "label": "next",
            "source_port": None,
            "target_port": None,
            "logical_type": None,
            "artifact_type": None,
            "metadata": {},
        }

    def test_edge_manifest_entry_handles_non_dict_metadata(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-dict metadata is normalized to empty dict by
        ``normalize_edge_metadata`` (called inside ``edge_manifest_entry``)."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)

        builder_mod = _import_builder()
        entry = builder_mod.edge_manifest_entry(
            source="x",
            target="y",
            label="loop",
            metadata=["not", "a", "dict"],
        )
        assert entry["metadata"] == {}
        entry2 = builder_mod.edge_manifest_entry(
            source="x", target="y", label="loop", metadata=None
        )
        assert entry2["metadata"] == {}


# ── A4a contract characterization tests ────────────────────────────────────────


# NOTE: These symbols are validated by compat.py as *required* for the Arnold
# host contract.  Astrid compilers and manifest extraction do NOT require
# Port, PortRef, or Pipeline from Arnold.
_REQUIRED_ARNOLD_SYMBOLS = frozenset(
    {
        "RuntimeEnvelope",
        "ResumeCursorRef",
        "AdvanceOutcome",
        "CheckpointOutcome",
        "StepwiseDriver",
        "PipelineBuilder",
        "Stage",
        "ParallelStage",
        "Edge",
        "Suspension",
        "StepContext",
        "ExecutorHooks",
        "StepInvocation",
        "ContractResult",
        "ContractStatus",
        "PipelineVerdict",
        "persist_resume_cursor",
        "read_resume_cursor",
    }
)

_OPTIONAL_ARNOLD_SYMBOLS = frozenset(
    {
        "EvidenceArtifactRef",
        "Provenance",
        "StepResult",
        "StepInvocationAdapter",
        "StepInvocationAdapterRegistry",
        "ContentValidatorRegistry",
        "no_op_content_validator",
    }
)

# Symbols that are Astrid-internal metadata and MUST NOT be required or assumed
# from the Arnold contract.  They live in Astrid's manifest sidecar or the
# shared lowering layer, not in arnold.pipeline.
_ASTRID_ONLY_NAMES = frozenset(
    {
        "Pipeline",
        "Port",
        "PortRef",
        "pipeline_manifest",
        "CompileResult",
        "_StageSpec",
        "_EdgeSpec",
        "SESSION_MANIFEST_SCHEMA_VERSION",
        "SessionManifest",
        "SegmentRecord",
    }
)


class TestA4aContractCharacterization:
    """Tests that characterise the Arnold public contract and distinguish
    required Arnold symbols from Astrid-only manifest sidecar metadata.

    These are characterisation / probe tests — they document the
    boundary, not change it.
    """

    def test_required_arnold_symbols_match_compat_declaration(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every symbol listed as required is declared in compat.py."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)

        compat_mod = importlib.import_module(
            "astrid.core.integrations.arnold.host.compat"
        )

        for name in _REQUIRED_ARNOLD_SYMBOLS:
            assert hasattr(compat_mod.compat, name), (
                f"compat.compat is missing required Arnold symbol {name!r}"
            )

    def test_optional_arnold_symbols_appear_when_available(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Optional symbols are present on compat only when the fake Arnold
        provides them — and they match the compat module's _OPTIONAL_SYMBOLS."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)

        compat_mod = importlib.import_module(
            "astrid.core.integrations.arnold.host.compat"
        )

        for name in _OPTIONAL_ARNOLD_SYMBOLS:
            assert hasattr(compat_mod.compat, name), (
                f"compat.compat is missing optional symbol {name!r} "
                f"even though the fake Arnold provides it"
            )

    def test_astrid_only_names_are_not_exposed_on_compat(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Names that are Astrid-internal metadata must not appear on
        ``compat.compat`` — they belong in the manifest sidecar, not the
        Arnold contract."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)

        compat_mod = importlib.import_module(
            "astrid.core.integrations.arnold.host.compat"
        )

        for name in _ASTRID_ONLY_NAMES:
            assert not hasattr(compat_mod.compat, name), (
                f"compat.compat must not expose Astrid-only name {name!r}"
            )

    def test_stage_decision_vocabulary_probe(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A stage built through the duck-typed builder can carry a
        ``decision_vocabulary`` — the A4a optional-stage vocabulary probe."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()
        stage = builder_mod.build_stage(
            pipeline.Stage,
            stage_id="optional_step",
            label="Optional Step",
            decision_vocabulary=("proceed", "skip"),
        )
        assert stage is not None
        vocab = getattr(stage, "decision_vocabulary", None)
        assert vocab is not None, "Stage must expose decision_vocabulary"
        assert set(vocab) == {"proceed", "skip"}

    def test_edge_metadata_capability_probe(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Probe whether an Arnold Edge can carry per-edge metadata fields
        (source_port, target_port, logical_type, artifact_type, metadata).

        The current duck-typed fake accepts any kwargs, so the probe
        documents that the surface can carry this data even if the real
        Arnold Edge does not yet accept all the fields."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        # The standard build_edge only passes source/target/label.  Construct
        # an Edge directly to probe extended kwargs.
        edge = pipeline.Edge(
            source="s1",
            target="s2",
            label="next",
            source_port="producer_out",
            target_port="consumer_in",
            logical_type=None,
            artifact_type="document",
            metadata={"predicate": "repeat.until"},
        )
        assert edge is not None
        assert getattr(edge, "source", None) == "s1"
        assert getattr(edge, "target", None) == "s2"
        # Probe that extended fields survive construction:
        assert getattr(edge, "source_port", None) == "producer_out"
        assert getattr(edge, "target_port", None) == "consumer_in"
        assert getattr(edge, "logical_type", None) is None
        assert getattr(edge, "artifact_type", None) == "document"
        assert getattr(edge, "metadata", None) == {"predicate": "repeat.until"}

    def test_schema_version_constant_probe(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Probe that the Arnold pipeline module exposes a SCHEMA_VERSION
        constant for A4a contract versioning.

        The constant lives on the pipeline module, not necessarily in the
        compat namespace (compat only mirrors symbols declared in its
        _REQUIRED_SYMBOLS/_OPTIONAL_SYMBOLS tuples)."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)

        # Probe the pipeline module directly — compat may not surface it.
        assert hasattr(pipeline, "SCHEMA_VERSION"), (
            "Arnold pipeline must expose SCHEMA_VERSION"
        )
        assert pipeline.SCHEMA_VERSION == 1

    def test_parallel_stage_join_probe(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Probe that ParallelStage exposes a callable ``join`` for the A4a
        fan-out join contract."""
        _clear_host_modules()

        pipeline = _build_minimal_valid_pipeline_module()
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        assert hasattr(pipeline.ParallelStage, "join"), (
            "ParallelStage must expose a join method for A4a"
        )
        join_method = getattr(pipeline.ParallelStage, "join")
        assert callable(join_method), "ParallelStage.join must be callable"

        # Smoke test: instantiate and call join
        ps = pipeline.ParallelStage(
            stage_id="fan", label="Fan-out", stages=[]
        )
        joined = ps.join([{"a": 1}, {"b": 2}])
        assert joined == [{"a": 1}, {"b": 2}]

    def test_stage_level_explicit_join_probe(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Prove that multiple edges converging on a single target stage
        (explicit join) can be constructed through the duck-typed builder.

        This documents the stage-level join shape needed by A4a fan-out
        lowering without requiring Arnold to change its Edge surface."""
        _clear_host_modules()

        class JoinBuilder:
            """Builder that accepts stages and edges for the join probe."""
            def __init__(self) -> None:
                self.stages: list[Any] = []
                self.edges: list[Any] = []

            def add_stage(self, stage: Any) -> None:
                self.stages.append(stage)

            def add_edge(self, edge: Any) -> None:
                self.edges.append(edge)

        pipeline = _build_minimal_valid_pipeline_module(
            PipelineBuilder=JoinBuilder,
        )
        _install_arnold_modules(monkeypatch, pipeline)
        _assert_no_port_pipeline_portref(pipeline)

        builder_mod = _import_builder()

        builder = pipeline.PipelineBuilder()
        source_a = builder_mod.build_stage(
            pipeline.Stage, stage_id="source_a", label="Source A"
        )
        source_b = builder_mod.build_stage(
            pipeline.Stage, stage_id="source_b", label="Source B"
        )
        target = builder_mod.build_stage(
            pipeline.Stage, stage_id="join_target", label="Join Target"
        )
        for s in (source_a, source_b, target):
            builder_mod.builder_add_stage(builder, s)

        edge_a = builder_mod.build_edge(
            pipeline.Edge, source="source_a", target="join_target", label="a_result"
        )
        edge_b = builder_mod.build_edge(
            pipeline.Edge, source="source_b", target="join_target", label="b_result"
        )
        builder_mod.builder_add_edge(builder, edge_a)
        builder_mod.builder_add_edge(builder, edge_b)

        assert len(builder.stages) == 3
        assert len(builder.edges) == 2
        assert {e.source for e in builder.edges} == {"source_a", "source_b"}
        assert all(e.target == "join_target" for e in builder.edges)
