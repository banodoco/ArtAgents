"""Tests for the Arnold authoring facade.

Covers:
- ``port()`` and ``artifact_ref()`` constructors
- ``executor_step()`` and ``wrapper_step()`` descriptor shapes
- ``opaque_stage_orchestrator()`` StageSpec output
- ``build_workflow()`` linear pipeline compilation
"""

from __future__ import annotations

import pytest

from astrid.core.integrations.arnold.session.authoring import (
    ArtifactRef,
    Port,
    artifact_ref,
    build_workflow,
    executor_step,
    opaque_stage_orchestrator,
    port,
    wrapper_step,
)
from astrid.core.integrations.arnold.session.lowering import StageSpec


class TestPortAndArtifactRef:
    """Thin constructors return correct types and values."""

    def test_port_constructor(self) -> None:
        p = port("video", artifact_type="video/mp4", description="Source video")
        assert isinstance(p, Port)
        assert p.name == "video"
        assert p.artifact_type == "video/mp4"
        assert p.description == "Source video"

    def test_port_minimal(self) -> None:
        p = port("audio")
        assert p.name == "audio"
        assert p.artifact_type is None
        assert p.description is None

    def test_port_metadata(self) -> None:
        p = port("config", required=True, default="value")
        assert p.metadata == {"required": True, "default": "value"}

    def test_artifact_ref_constructor(self) -> None:
        ref = artifact_ref("template_output", "ados-sunday-template.json", artifact_type="application/json")
        assert isinstance(ref, ArtifactRef)
        assert ref.name == "template_output"
        assert ref.path == "ados-sunday-template.json"
        assert ref.artifact_type == "application/json"

    def test_artifact_ref_minimal(self) -> None:
        ref = artifact_ref("search_output", "search-results.txt")
        assert ref.name == "search_output"
        assert ref.path == "search-results.txt"
        assert ref.artifact_type is None


class TestExecutorStep:
    """Executor step descriptors have correct shape."""

    def test_executor_step_minimal(self) -> None:
        desc = executor_step("step1", segment_id="test.seg", adapter="local")
        assert desc["kind"] == "executor"
        assert desc["stage_id"] == "step1"
        assert desc["segment_id"] == "test.seg"
        assert desc["adapter"] == "local"
        assert desc["label"] == "step1"

    def test_executor_step_with_produces(self) -> None:
        desc = executor_step(
            "render",
            segment_id="video_editing.event_talks",
            adapter="local",
            command="python3 -m render",
            produces={"output": "render-manifest.json"},
        )
        assert desc["produces"] == {"output": "render-manifest.json"}

    def test_executor_step_with_consumes(self) -> None:
        desc = executor_step(
            "step2",
            segment_id="test.seg",
            adapter="local",
            consumes={"source": "$.video"},
        )
        assert desc["consumes"] == {"source": "$.video"}

    def test_executor_step_custom_label(self) -> None:
        desc = executor_step("step1", segment_id="test.seg", label="My Step")
        assert desc["label"] == "My Step"
        assert desc["stage_id"] == "step1"


class TestWrapperStep:
    """Wrapper step descriptors have correct shape."""

    def test_wrapper_step_minimal(self) -> None:
        desc = wrapper_step(
            "validate",
            segment_id="test.seg",
            path=("test.seg", "validate"),
        )
        assert desc["kind"] == "wrapper"
        assert desc["stage_id"] == "validate"
        assert desc["path"] == ("test.seg", "validate")
        assert desc["adapter"] == "orchestrator"

    def test_wrapper_step_with_command(self) -> None:
        desc = wrapper_step(
            "edit-image",
            segment_id="video_editing.animate_image",
            path=("video_editing.animate_image", "edit-image"),
            command="edit-image",
        )
        assert desc["command"] == "edit-image"


class TestOpaqueStageOrchestrator:
    """opaque_stage_orchestrator returns a correct lowering.StageSpec."""

    def test_returns_stage_spec(self) -> None:
        spec = opaque_stage_orchestrator(
            "dataset-build",
            segment_id="training.dataset_build",
            path="training.dataset_build",
            adapter="local",
            command="python3 -m train",
        )
        assert isinstance(spec, StageSpec)
        assert spec.stage_id == "dataset-build"
        assert spec.label == "dataset-build"

    def test_wrapper_metadata_carries_adapter_command_path(self) -> None:
        spec = opaque_stage_orchestrator(
            "training-run",
            segment_id="training.training_run",
            path=("training", "training_run"),
            adapter="orchestrator",
            command="python3 -m train",
        )
        assert spec.metadata["adapter"] == "orchestrator"
        assert spec.metadata["command"] == "python3 -m train"
        assert spec.metadata["source_plan_path"] == ["training", "training_run"]
        assert spec.metadata["wrapper_runtime"] == "command"
        assert spec.metadata["wrapper_orchestrator_id"] == "training.training_run"
        assert spec.metadata["wrapper_subcommand"] == "training-run"

    def test_produces_populated(self) -> None:
        spec = opaque_stage_orchestrator(
            "dataset-build",
            segment_id="training.dataset_build",
            path="training.dataset_build",
            adapter="local",
            command="python3 -m build",
            produces={"dataset": "dataset.zip"},
        )
        assert "produces" in spec.metadata
        assert "dataset.zip" in spec.metadata["produces"]

    def test_consumes_populated(self) -> None:
        spec = opaque_stage_orchestrator(
            "dataset-build",
            segment_id="training.dataset_build",
            path="training.dataset_build",
            adapter="local",
            command="python3 -m build",
            consumes={"config": "$.config"},
        )
        assert "consumes" in spec.metadata
        assert spec.metadata["consumes"] == {"config": "$.config"}

    def test_custom_label(self) -> None:
        spec = opaque_stage_orchestrator(
            "dataset-build",
            segment_id="training.dataset_build",
            path="training.dataset_build",
            adapter="local",
            command="python3 -m build",
            label="Build Dataset",
        )
        assert spec.label == "Build Dataset"

    def test_string_path_becomes_tuple(self) -> None:
        spec = opaque_stage_orchestrator(
            "dataset-build",
            segment_id="training.dataset_build",
            path="training.dataset_build",
            adapter="local",
            command="python3 -m build",
        )
        assert spec.metadata["source_plan_path"] == ["training", "dataset_build"]

    def test_tuple_path_preserved(self) -> None:
        spec = opaque_stage_orchestrator(
            "run",
            segment_id="training.training_run",
            path=("training", "training_run", "main"),
            adapter="orchestrator",
            command="python3 -m run",
        )
        assert spec.metadata["source_plan_path"] == ["training", "training_run", "main"]

    def test_metadata_merged(self) -> None:
        spec = opaque_stage_orchestrator(
            "step",
            segment_id="test.seg",
            path="test.seg",
            adapter="local",
            command="echo hi",
            metadata={"extra_key": "extra_value", "priority": 1},
        )
        assert spec.metadata["extra_key"] == "extra_value"
        assert spec.metadata["priority"] == 1

    def test_decision_vocabulary_defaults_to_next(self) -> None:
        spec = opaque_stage_orchestrator(
            "step",
            segment_id="test.seg",
            path="test.seg",
            adapter="local",
            command="echo hi",
        )
        assert spec.decision_vocabulary == ("next",)
        assert spec.metadata["vocabulary"] == ["next"]

    def test_invocation_is_none(self) -> None:
        """Opaque stages have no invocation — they are wrapper-runtime."""
        spec = opaque_stage_orchestrator(
            "step",
            segment_id="test.seg",
            path="test.seg",
            adapter="local",
            command="echo hi",
        )
        assert spec.invocation is None


class TestBuildWorkflow:
    """build_workflow compiles linear executor pipelines."""

    def test_builds_five_stage_pipeline(self) -> None:
        steps = [
            executor_step("step1", segment_id="test.wf", adapter="local", command="echo 1"),
            executor_step("step2", segment_id="test.wf", adapter="local", command="echo 2"),
            executor_step("step3", segment_id="test.wf", adapter="local", command="echo 3"),
        ]
        pipeline = build_workflow(steps, segment_id="test.wf")
        stage_ids = list(pipeline.stages.keys())
        assert stage_ids == ["step1", "step2", "step3", "halt"]
        assert pipeline.entry_stage_id == "step1"

    def test_empty_stages_returns_halt_only(self) -> None:
        pipeline = build_workflow([], segment_id="test.wf")
        stage_ids = list(pipeline.stages.keys())
        assert stage_ids == ["halt"]
        assert pipeline.entry_stage_id == "halt"

    def test_edges_are_linear_next(self) -> None:
        steps = [
            executor_step("a", segment_id="test.wf", adapter="local", command="echo a"),
            executor_step("b", segment_id="test.wf", adapter="local", command="echo b"),
        ]
        pipeline = build_workflow(steps, segment_id="test.wf")
        # Edges are stored per-stage
        edges = []
        for stage_id, stage in pipeline.stages.items():
            if hasattr(stage, 'edges'):
                for edge in stage.edges:
                    edges.append((getattr(edge, 'source', '?'), getattr(edge, 'target', '?'), getattr(edge, 'label', '?')))
        assert ("a", "b", "next") in edges
        assert ("b", "halt", "next") in edges

    def test_workflow_with_wrapper_stages(self) -> None:
        steps = [
            executor_step("exec1", segment_id="test.wf", adapter="local", command="echo exec"),
            wrapper_step("wrap1", segment_id="test.wf", path=("test.wf", "wrap1"), command="wrap-cmd"),
            executor_step("exec2", segment_id="test.wf", adapter="local", command="echo exec2"),
        ]
        pipeline = build_workflow(steps, segment_id="test.wf")
        stage_ids = list(pipeline.stages.keys())
        assert "exec1" in stage_ids
        assert "wrap1" in stage_ids
        assert "exec2" in stage_ids
        assert "halt" in stage_ids
