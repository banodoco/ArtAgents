from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.execution.executor.schema import load_executor_manifest
from astrid.core.gateway.dispatch import _top_level_commands
from astrid.packs.vibecomfy.executors._workflow_ir import (
    WorkflowIrBridgeError,
    edit_workflow,
    inspect_workflow,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "vibecomfy_ir" / "flat.json"
EXECUTORS = ROOT / "astrid" / "packs" / "vibecomfy" / "executors"


def _require_vibecomfy() -> None:
    pytest.importorskip("vibecomfy")


def _write_operations(path: Path, ops: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, "expected_revision": 0, "ops": ops}),
        encoding="utf-8",
    )


def test_ir_executors_are_manifested_without_growing_the_gateway() -> None:
    inspect_manifest = load_executor_manifest(EXECUTORS / "inspect" / "executor.yaml")
    edit_manifest = load_executor_manifest(EXECUTORS / "edit" / "executor.yaml")

    assert inspect_manifest.id == "vibecomfy.inspect"
    assert edit_manifest.id == "vibecomfy.edit"
    assert inspect_manifest.isolation.network is False
    assert edit_manifest.isolation.network is False
    assert {output.name for output in inspect_manifest.outputs} == {
        "projection",
        "inspection",
    }
    assert {output.name for output in edit_manifest.outputs} == {
        "workflow",
        "projection",
        "report",
    }
    assert _top_level_commands() == frozenset(
        {
        "projects",
        "timelines",
        "media",
        "tasks",
        "runs",
        "doctor",
        "backup",
        }
    )


def test_inspect_emits_projection_without_mutating_ui_graph(tmp_path: Path) -> None:
    _require_vibecomfy()
    before = FIXTURE.read_bytes()

    outputs = inspect_workflow(FIXTURE, tmp_path / "inspection")

    assert FIXTURE.read_bytes() == before
    assert "ksampler" in outputs["projection"].read_text(encoding="utf-8")
    report = json.loads(outputs["inspection"].read_text(encoding="utf-8"))
    assert report["authority"] == "input_ui_graph"
    assert report["projection"] == "read_only_python_like_ir"
    assert report["source_sha256"].startswith("sha256:")
    assert report["lenses"]["topology"]


def test_edit_applies_one_atomic_typed_batch_and_emits_fresh_projection(
    tmp_path: Path,
) -> None:
    _require_vibecomfy()
    operations = tmp_path / "operations.json"
    _write_operations(
        operations,
        [
            {"op": "edit_node", "target": "ksampler", "field": "steps", "value": 25},
            {"op": "set_node_mode", "target": "ksampler", "mode": "bypassed"},
        ],
    )

    outputs = edit_workflow(FIXTURE, operations, tmp_path / "edited")

    edited = json.loads(outputs["workflow"].read_text(encoding="utf-8"))
    sampler = next(node for node in edited["nodes"] if node["type"] == "KSampler")
    assert sampler["widgets_values"][2] == 25
    assert sampler["mode"] == 4
    assert "steps=25" in outputs["projection"].read_text(encoding="utf-8")
    report = json.loads(outputs["report"].read_text(encoding="utf-8"))
    assert report["authority"] == "input_ui_graph_plus_typed_delta"
    assert report["revision"] == 1
    assert report["requested_tools"] == ["edit_node", "set_node_mode"]
    assert report["source_sha256"] != report["edited_sha256"]
    assert len(report["canonical_delta"]) == 2


def test_edit_rejects_projection_rewrites_before_creating_outputs(tmp_path: Path) -> None:
    _require_vibecomfy()
    operations = tmp_path / "operations.json"
    _write_operations(
        operations,
        [{"op": "exec_python", "source": "ksampler.steps = 25"}],
    )
    out_dir = tmp_path / "edited"

    with pytest.raises(WorkflowIrBridgeError, match="must be one of"):
        edit_workflow(FIXTURE, operations, out_dir)

    assert not out_dir.exists()


def test_edit_rejects_nested_batches_before_creating_outputs(tmp_path: Path) -> None:
    _require_vibecomfy()
    operations = tmp_path / "operations.json"
    _write_operations(
        operations,
        [{"op": "edit_batch", "ops": [{"op": "remove_node", "target": "preview"}]}],
    )
    out_dir = tmp_path / "edited"

    with pytest.raises(WorkflowIrBridgeError, match="must be one of"):
        edit_workflow(FIXTURE, operations, out_dir)

    assert not out_dir.exists()


def test_edit_rejects_a_stale_expected_revision(tmp_path: Path) -> None:
    _require_vibecomfy()
    operations = tmp_path / "operations.json"
    operations.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "expected_revision": 1,
                "ops": [
                    {"op": "edit_node", "target": "ksampler", "field": "steps", "value": 25}
                ],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "edited"

    with pytest.raises(WorkflowIrBridgeError, match="typed edit rejected"):
        edit_workflow(FIXTURE, operations, out_dir)

    assert not out_dir.exists()


def test_edit_batch_is_atomic_when_any_leaf_operation_is_invalid(tmp_path: Path) -> None:
    _require_vibecomfy()
    operations = tmp_path / "operations.json"
    _write_operations(
        operations,
        [
            {"op": "edit_node", "target": "ksampler", "field": "steps", "value": 25},
            {"op": "edit_node", "target": "missing-node", "field": "steps", "value": 26},
        ],
    )
    out_dir = tmp_path / "edited"

    with pytest.raises(WorkflowIrBridgeError, match="typed edit rejected"):
        edit_workflow(FIXTURE, operations, out_dir)

    assert not out_dir.exists()
