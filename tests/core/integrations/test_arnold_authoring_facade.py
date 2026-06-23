"""Tests for the Arnold authoring facade.

Covers:
- ``executor_step()`` StageSpec construction
- ``edge()`` EdgeSpec construction
- ``halt()`` terminal StageSpec
- ``human_gate()`` StageSpec
- ``pipeline()`` compilation
- ``build_executor_argv()`` helper
- ``coerce_workflow_inputs()`` helper
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.integrations.arnold.authoring import (
    build_executor_argv,
    coerce_workflow_inputs,
    edge,
    executor_step,
    halt,
    human_gate,
    pipeline,
)
from astrid.core.integrations.arnold.session.lowering import EdgeSpec, StageSpec


class TestExecutorStep:
    """executor_step returns StageSpec with correct attributes."""

    def test_executor_step_minimal(self) -> None:
        spec = executor_step(
            stage_id="step1",
            label="Step 1",
            executor_id="task.local",
            segment_id="test.seg",
            project="default",
            run_root=Path("/tmp/test"),
        )
        assert isinstance(spec, StageSpec)
        assert spec.stage_id == "step1"
        assert spec.label == "Step 1"

    def test_executor_step_with_command(self) -> None:
        spec = executor_step(
            stage_id="render",
            label="Render",
            executor_id="task.local",
            segment_id="video_editing.event_talks",
            project="default",
            run_root=Path("/tmp/test"),
            command="python3 -m render",
        )
        assert spec.metadata.get("command") == "python3 -m render"

    def test_executor_step_with_outputs(self) -> None:
        spec = executor_step(
            stage_id="render",
            label="Render",
            executor_id="task.local",
            segment_id="video_editing.event_talks",
            project="default",
            run_root=Path("/tmp/test"),
            outputs={"output": "render-manifest.json"},
        )
        assert "produces" in spec.metadata
        assert "output" in spec.metadata["produces"]

    def test_executor_step_with_inputs(self) -> None:
        spec = executor_step(
            stage_id="step2",
            label="Step 2",
            executor_id="task.local",
            segment_id="test.seg",
            project="default",
            run_root=Path("/tmp/test"),
            inputs={"source": "path/to/file"},
        )
        assert spec.metadata is not None

    def test_executor_step_decision_vocabulary_default(self) -> None:
        spec = executor_step(
            stage_id="step1",
            label="Step 1",
            executor_id="task.local",
            segment_id="test.seg",
            project="default",
            run_root=Path("/tmp/test"),
        )
        assert "next" in spec.decision_vocabulary

    def test_executor_step_optional(self) -> None:
        spec = executor_step(
            stage_id="step1",
            label="Step 1",
            executor_id="task.local",
            segment_id="test.seg",
            project="default",
            run_root=Path("/tmp/test"),
            optional=True,
        )
        # Optional steps populate vocabulary in metadata (decision_vocabulary
        # on StageSpec is set by lowering, which defaults to ('next',)).
        vocab = spec.metadata.get("vocabulary", [])
        assert "proceed" in vocab
        assert "skip" in vocab

    def test_executor_step_requires_ack(self) -> None:
        spec = executor_step(
            stage_id="step1",
            label="Step 1",
            executor_id="task.local",
            segment_id="test.seg",
            project="default",
            run_root=Path("/tmp/test"),
            requires_ack=True,
        )
        assert spec.metadata.get("requires_ack") is True

    def test_executor_step_metadata_merged(self) -> None:
        spec = executor_step(
            stage_id="step1",
            label="Step 1",
            executor_id="task.local",
            segment_id="test.seg",
            project="default",
            run_root=Path("/tmp/test"),
            metadata={"extra_key": "extra_value"},
        )
        assert spec.metadata.get("extra_key") == "extra_value"


class TestEdge:
    """edge returns EdgeSpec with correct attributes."""

    def test_edge_minimal(self) -> None:
        e = edge(source="step1", target="step2")
        assert isinstance(e, EdgeSpec)
        assert e.source == "step1"
        assert e.target == "step2"
        assert e.label == "next"

    def test_edge_with_custom_label(self) -> None:
        e = edge(source="step1", target="step2", label="approve")
        assert e.label == "approve"

    def test_edge_with_ports(self) -> None:
        e = edge(
            source="a",
            target="b",
            source_port="out",
            target_port="in",
        )
        assert e.source_port == "out"
        assert e.target_port == "in"

    def test_edge_with_logical_and_artifact_type(self) -> None:
        e = edge(
            source="a",
            target="b",
            logical_type="video",
            artifact_type="video/mp4",
        )
        assert e.metadata.get("logical_type") == "video"
        assert e.metadata.get("artifact_type") == "video/mp4"

    def test_edge_metadata_merged(self) -> None:
        e = edge(source="a", target="b", metadata={"priority": 1})
        assert e.metadata.get("priority") == 1


class TestHalt:
    """halt returns a terminal StageSpec."""

    def test_halt_returns_stage_spec(self) -> None:
        h = halt()
        assert isinstance(h, StageSpec)

    def test_halt_has_halt_stage_id(self) -> None:
        h = halt()
        from astrid.core.integrations.arnold.session.lowering import HALT_STAGE_ID
        assert h.stage_id == HALT_STAGE_ID


class TestHumanGate:
    """human_gate returns a StageSpec with human_gate metadata."""

    def test_human_gate_returns_stage_spec(self) -> None:
        spec = human_gate(
            stage_id="gate1",
            label="Review Gate",
            segment_id="test.seg",
        )
        assert isinstance(spec, StageSpec)
        assert spec.stage_id == "gate1"
        assert spec.label == "Review Gate"

    def test_human_gate_has_human_gate_metadata(self) -> None:
        spec = human_gate(
            stage_id="gate1",
            label="Review Gate",
            segment_id="test.seg",
        )
        assert spec.metadata.get("human_gate") is True
        assert spec.metadata.get("manual") is True
        assert spec.metadata.get("requires_ack") is True

    def test_human_gate_default_decision_routes(self) -> None:
        spec = human_gate(
            stage_id="gate1",
            label="Review Gate",
            segment_id="test.seg",
        )
        assert "approve" in spec.decision_vocabulary

    def test_human_gate_custom_decision_routes(self) -> None:
        spec = human_gate(
            stage_id="gate1",
            label="Review Gate",
            segment_id="test.seg",
            decision_routes={"approve": "next", "reject": "repeat"},
        )
        assert "approve" in spec.decision_vocabulary
        assert "reject" in spec.decision_vocabulary
        assert spec.metadata.get("decision_routes") == {
            "approve": "next",
            "reject": "repeat",
        }


class TestPipeline:
    """pipeline compiles StageSpec and EdgeSpec tuples into a Pipeline.

    Note: pipeline() compilation hits a pre-existing builder.py suspension
    bug (T3 scope) — ``TypeError: Stage.__init__() got an unexpected keyword
    argument 'suspension'``.  The StageSpec and EdgeSpec construction is
    verified directly; full pipeline compilation is tested here with the
    expected pre-existing error acknowledged.
    """

    def test_pipeline_compilation_hits_pre_existing_builder_bug(self) -> None:
        """pipeline() now compiles successfully with the real Arnold builder."""
        s1 = executor_step(
            stage_id="step1",
            label="Step 1",
            executor_id="task.local",
            segment_id="test.wf",
            project="default",
            run_root=Path("/tmp/test"),
            command="echo 1",
            outputs={"out1": "step1.json"},
        )
        s2 = executor_step(
            stage_id="step2",
            label="Step 2",
            executor_id="task.local",
            segment_id="test.wf",
            project="default",
            run_root=Path("/tmp/test"),
            command="echo 2",
            outputs={"out2": "step2.json"},
        )
        h = halt()

        e1 = edge(source="step1", target="step2", label="next")
        e2 = edge(source="step2", target=h.stage_id, label="next")

        p = pipeline(
            entry_stage_id="step1",
            stages=(s1, s2, h),
            edges=(e1, e2),
        )
        assert p is not None
        assert "step1" in p.stages
        assert "step2" in p.stages
        assert h.stage_id in p.stages


class TestBuildExecutorArgv:
    """build_executor_argv produces correct argv lists."""

    def test_basic_module(self) -> None:
        argv = build_executor_argv(module="my.pack.run")
        assert argv == ["python3", "-m", "my.pack.run"]

    def test_with_subcommand(self) -> None:
        argv = build_executor_argv(
            module="my.pack.run",
            subcommand="render",
        )
        assert argv == ["python3", "-m", "my.pack.run", "render"]

    def test_with_extra_args(self) -> None:
        argv = build_executor_argv(
            module="my.pack.run",
            subcommand="render",
            extra_args=["--out", "/tmp/out.json"],
        )
        assert argv == [
            "python3",
            "-m",
            "my.pack.run",
            "render",
            "--out",
            "/tmp/out.json",
        ]

    def test_custom_python_exec(self) -> None:
        argv = build_executor_argv(
            python_exec="python3.11",
            module="my.pack.run",
        )
        assert argv == ["python3.11", "-m", "my.pack.run"]


class TestCoerceWorkflowInputs:
    """coerce_workflow_inputs validates and defaults inputs against a schema."""

    def test_required_input_present(self) -> None:
        schema = {"name": {"type": "str", "required": True}}
        result = coerce_workflow_inputs(raw_inputs={"name": "test"}, schema=schema)
        assert result == {"name": "test"}

    def test_required_input_missing_raises(self) -> None:
        schema = {"name": {"type": "str", "required": True}}
        import pytest
        with pytest.raises(ValueError, match="Missing required workflow input"):
            coerce_workflow_inputs(raw_inputs={}, schema=schema)

    def test_optional_input_with_default(self) -> None:
        schema = {"count": {"type": "int", "default": 5}}
        result = coerce_workflow_inputs(raw_inputs={}, schema=schema)
        assert result == {"count": 5}

    def test_type_coercion_int(self) -> None:
        schema = {"count": {"type": "int"}}
        result = coerce_workflow_inputs(raw_inputs={"count": "42"}, schema=schema)
        assert result == {"count": 42}

    def test_type_coercion_float(self) -> None:
        schema = {"score": {"type": "float"}}
        result = coerce_workflow_inputs(raw_inputs={"score": "3.14"}, schema=schema)
        assert result == {"score": 3.14}

    def test_type_coercion_bool(self) -> None:
        schema = {"verbose": {"type": "bool"}}
        result = coerce_workflow_inputs(raw_inputs={"verbose": "true"}, schema=schema)
        assert result == {"verbose": True}

    def test_type_coercion_path(self) -> None:
        schema = {"out_dir": {"type": "path"}}
        result = coerce_workflow_inputs(
            raw_inputs={"out_dir": "/tmp/out"}, schema=schema
        )
        assert result == {"out_dir": Path("/tmp/out")}

    def test_overrides_default_with_raw_input(self) -> None:
        schema = {"count": {"type": "int", "default": 5}}
        result = coerce_workflow_inputs(raw_inputs={"count": 10}, schema=schema)
        assert result == {"count": 10}
