"""Tests for OrchestratorDefinition input/output artifact_type accessors
and child-type validation in the orchestrator registry.
"""

from __future__ import annotations

from astrid.core.contracts.schema import Output, Port
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec


class TestOrchestratorDefinitionArtifactTypes:
    """input_artifact_types() and output_artifact_types() accessors."""

    def test_input_artifact_types_returns_frozenset_of_non_null_types(self) -> None:
        orch = OrchestratorDefinition(
            id="test.id",
            name="Test Orch",
            kind="built_in",
            version="1.0",
            runtime=RuntimeSpec(kind="python", function="main"),
            inputs=(
                Port(name="prompt_in", artifact_type="prompt"),
                Port(name="audio_in", artifact_type="audio"),
                Port(name="mode_in", artifact_type=None),
                Port(name="image_ref", artifact_type="image"),
            ),
        )
        result = orch.input_artifact_types()
        assert isinstance(result, frozenset)
        assert result == frozenset({"prompt", "audio", "image"})

    def test_input_artifact_types_empty_when_no_types_declared(self) -> None:
        orch = OrchestratorDefinition(
            id="test.id",
            name="Test Orch",
            kind="built_in",
            version="1.0",
            runtime=RuntimeSpec(kind="python", function="main"),
            inputs=(
                Port(name="a"),
                Port(name="b"),
            ),
        )
        result = orch.input_artifact_types()
        assert isinstance(result, frozenset)
        assert result == frozenset()

    def test_input_artifact_types_empty_when_no_inputs(self) -> None:
        orch = OrchestratorDefinition(
            id="test.id",
            name="Test Orch",
            kind="built_in",
            version="1.0",
            runtime=RuntimeSpec(kind="python", function="main"),
        )
        result = orch.input_artifact_types()
        assert isinstance(result, frozenset)
        assert result == frozenset()

    def test_output_artifact_types_returns_frozenset_of_non_null_types(self) -> None:
        orch = OrchestratorDefinition(
            id="test.id",
            name="Test Orch",
            kind="built_in",
            version="1.0",
            runtime=RuntimeSpec(kind="python", function="main"),
            outputs=(
                Output(name="video_out", artifact_type="video/clip"),
                Output(name="transcript_out", artifact_type="transcript"),
                Output(name="manifest_out", artifact_type=None),
                Output(name="pool_out", artifact_type="pool"),
            ),
        )
        result = orch.output_artifact_types()
        assert isinstance(result, frozenset)
        assert result == frozenset({"video/clip", "transcript", "pool"})

    def test_output_artifact_types_empty_when_no_types_declared(self) -> None:
        orch = OrchestratorDefinition(
            id="test.id",
            name="Test Orch",
            kind="built_in",
            version="1.0",
            runtime=RuntimeSpec(kind="python", function="main"),
            outputs=(
                Output(name="a"),
                Output(name="b"),
            ),
        )
        result = orch.output_artifact_types()
        assert isinstance(result, frozenset)
        assert result == frozenset()

    def test_output_artifact_types_empty_when_no_outputs(self) -> None:
        orch = OrchestratorDefinition(
            id="test.id",
            name="Test Orch",
            kind="built_in",
            version="1.0",
            runtime=RuntimeSpec(kind="python", function="main"),
        )
        result = orch.output_artifact_types()
        assert isinstance(result, frozenset)
        assert result == frozenset()
