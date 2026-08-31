import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator
from astrid.packs.video_editing.orchestrators.iteration_video import plan_template
from astrid.packs.video_editing.orchestrators.iteration_video import run as iteration_video

TARGET_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV1"
ROOT_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV2"


def test_iteration_video_inspect_does_not_render_or_summarize_and_suppresses_content(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    runtime = _runtime_client(include_root=True)

    def fail_render(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("inspect must not render")

    monkeypatch.setattr(iteration_video, "_runtime_client_context", lambda *_args: nullcontext(runtime))
    monkeypatch.setattr(iteration_video, "run_builtin_render", fail_render)

    report = iteration_video.inspect_iteration_run(repo_root=repo, target_run_id=TARGET_RUN_ID, project_slug="demo", runtime_client=runtime)
    text = iteration_video.format_inspection(report, no_content=True)

    assert report["summary_cache"] == {"hits": 0, "misses": 0}
    assert report["detected_modalities"] == ["image", "model_3d"]
    assert {item["renderer"] for item in report["chosen_renderers"]} == {"image_grid", "generic_card"}
    assert "Estimated cost: ~$0.000" in text
    assert "content: suppressed" in text
    assert "SECRET prompt" not in text


def test_iteration_lineage_quality_is_conservative_when_parent_ids_resolve() -> None:
    parent = iteration_video.RuntimeRunNode(
        run_id=ROOT_RUN_ID,
        record={"output_artifacts": [{"kind": "image"}]},
        depth=1,
        label="pulled_by_ancestry",
    )
    target = iteration_video.RuntimeRunNode(
        run_id=TARGET_RUN_ID,
        record={
            "output_artifacts": [{"kind": "image"}],
            "runtime_tasks_available": True,
            "task_records": [{"task_id": "task-target", "output_artifacts": [{"kind": "image"}]}],
            "runtime_relations_available": True,
            "runtime_run_events_available": True,
            "runtime_task_events_available": True,
            "runtime_evidence": [],
            "runtime_receipts": [],
            "runtime_lineage_gaps": ["evidence_unavailable", "receipts_unavailable"],
        },
        depth=0,
        label="target",
        parent_edges=[{"run_id": ROOT_RUN_ID, "kind": "causal"}],
    )
    _manifest, quality = iteration_video._build_runtime_inputs(
        [parent, target], target_run_id=TARGET_RUN_ID, project_slug="demo"
    )
    assert quality["data_quality"] < 1.0
    assert quality["missing_evidence"] == [ROOT_RUN_ID, TARGET_RUN_ID]
    assert quality["missing_receipts"] == [ROOT_RUN_ID, TARGET_RUN_ID]


def test_iteration_rejects_cross_project_runtime_run_without_leaking_data() -> None:
    class Runs:
        def list(self, project):
            assert project == "selected"
            return []

        def show(self, project, run_id):
            return {
                "run_id": run_id,
                "project_id": "other-project",
                "output_artifacts": [{"kind": "secret"}],
            }

    runtime = type("Runtime", (), {"runs": Runs()})()
    with pytest.raises(iteration_video.IterationVideoError, match="not selected project"):
        iteration_video.resolve_target_run_id(
            Path("."),
            target_run_id=TARGET_RUN_ID,
            project_slug="selected",
            runtime_client=runtime,
        )


def test_iteration_rejects_run_without_project_ownership() -> None:
    class Runs:
        def show(self, project, run_id):
            assert project == "selected"
            return {"run_id": run_id, "output_artifacts": [{"kind": "secret"}]}

    class Runtime:
        runs = Runs()

    with pytest.raises(iteration_video.IterationVideoError, match="no project ownership"):
        iteration_video._runtime_run_show(Runtime(), "selected", TARGET_RUN_ID)


def test_iteration_rejects_conflicting_run_project_owners() -> None:
    class Runs:
        def show(self, project, run_id):
            return {
                "run_id": run_id,
                "project_id": "selected",
                "project_slug": "other-project",
            }

    class Runtime:
        runs = Runs()

    with pytest.raises(iteration_video.IterationVideoError, match="not selected project"):
        iteration_video._runtime_run_show(Runtime(), "selected", TARGET_RUN_ID)


def test_iteration_does_not_use_unscoped_run_lookup() -> None:
    class Runtime:
        def get_run(self, run_id):
            raise AssertionError("unscoped get_run must not be used")

    assert iteration_video._runtime_run_show(Runtime(), "selected", TARGET_RUN_ID) is None


def test_iteration_only_uses_supported_known_run_relation_direction() -> None:
    relations = [
        {"from_run_id": TARGET_RUN_ID, "to_run_id": ROOT_RUN_ID, "kind": "derived_from"},
        {"from_run_id": "unrelated", "to_run_id": ROOT_RUN_ID, "kind": "derived_from"},
    ]
    selected, available = iteration_video._runtime_run_relations(
        relations, known_run_ids={TARGET_RUN_ID, ROOT_RUN_ID}
    )
    assert available is False
    assert selected == [
        {"from_run_id": TARGET_RUN_ID, "to_run_id": ROOT_RUN_ID, "kind": "derived_from"}
    ]
    _selected, available = iteration_video._runtime_run_relations(
        [{"from_run_id": TARGET_RUN_ID, "to_run_id": ROOT_RUN_ID, "kind": "mystery"}],
        known_run_ids={TARGET_RUN_ID, ROOT_RUN_ID},
    )
    assert available is False


def test_iteration_relation_media_objects_are_not_promoted_to_run_lineage() -> None:
    selected, available = iteration_video._runtime_run_relations(
        [{"from_object_id": "object-a", "to_object_id": "object-b", "kind": "derived_from"}],
        known_run_ids={TARGET_RUN_ID, ROOT_RUN_ID},
    )
    assert selected == []
    assert available is False


def test_iteration_events_drop_mismatched_aggregate_ids() -> None:
    class Runs:
        def events(self, project, run_id):
            return [
                {"event_id": "exact", "aggregate_id": run_id},
                {"event_id": "other", "aggregate_id": ROOT_RUN_ID},
            ]

    class Tasks:
        def events(self, task_id, project=None):
            return [
                {"event_id": "exact", "aggregate_id": task_id},
                {"event_id": "other", "aggregate_id": "task-other"},
            ]

    runtime = type("Runtime", (), {"runs": Runs(), "tasks": Tasks()})()
    run_events, run_available = iteration_video._runtime_run_events(runtime, "demo", TARGET_RUN_ID)
    task_events, task_available = iteration_video._runtime_task_events(runtime, "demo", "task-target")
    assert run_events == [{"event_id": "exact", "aggregate_id": TARGET_RUN_ID}]
    assert task_events == [{"event_id": "exact", "aggregate_id": "task-target"}]
    assert run_available is False
    assert task_available is False


def test_iteration_malformed_event_response_is_unavailable() -> None:
    class Runs:
        def events(self, project, run_id):
            return {"unexpected": "shape"}

    runtime = type("Runtime", (), {"runs": Runs()})()
    events, available = iteration_video._runtime_run_events(runtime, "demo", TARGET_RUN_ID)
    assert events == []
    assert available is False


def test_iteration_task_project_mismatch_is_not_attached() -> None:
    class Tasks:
        def list(self, project):
            return [{
                "task_id": "task-secret",
                "run_id": TARGET_RUN_ID,
                "project_id": "other-project",
                "output_artifacts": [{"kind": "secret"}],
            }]

    runtime = type("Runtime", (), {"tasks": Tasks()})()
    task_records, available = iteration_video._runtime_task_records(runtime, "selected")
    assert task_records == {}
    assert available is False


def test_iteration_task_without_project_ownership_is_not_attached() -> None:
    class Tasks:
        def list(self, project):
            return [{"task_id": "task-unowned", "run_id": TARGET_RUN_ID}]

    runtime = type("Runtime", (), {"tasks": Tasks()})()
    task_records, available = iteration_video._runtime_task_records(runtime, "selected")
    assert task_records == {}
    assert available is False


def test_iteration_rejects_conflicting_task_project_owners() -> None:
    class Tasks:
        def list(self, project):
            return [{
                "task_id": "task-bound",
                "run_id": TARGET_RUN_ID,
                "project_id": "selected",
                "project_slug": "other-project",
            }]

    runtime = type("Runtime", (), {"tasks": Tasks()})()
    task_records, available = iteration_video._runtime_task_records(runtime, "selected")
    assert task_records == {}
    assert available is False


def test_iteration_evidence_and_receipts_require_run_binding() -> None:
    run = {
        "run_id": TARGET_RUN_ID,
        "evidence": [{"id": "secret", "run_id": "other-run"}, {"id": "bound", "run_id": TARGET_RUN_ID}],
        "receipts": [{"id": "unbound", "run_id": "other-run"}, {"id": "bound-receipt", "run_id": TARGET_RUN_ID}],
    }
    attached_evidence = iteration_video._runtime_attached_values(run, [], "evidence")
    attached_receipts = iteration_video._runtime_attached_values(run, [], "receipts")
    assert attached_evidence == [{"id": "bound", "run_id": TARGET_RUN_ID}]
    assert attached_receipts == [{"id": "bound-receipt", "run_id": TARGET_RUN_ID}]


def test_iteration_rejects_task_mismatch_on_run_bound_fact() -> None:
    run = {
        "run_id": TARGET_RUN_ID,
        "task_ids": ["task-bound"],
        "runtime_run_events": [{
            "aggregate_id": TARGET_RUN_ID,
            "payload": {"evidence": [{"id": "wrong-task", "task_id": "task-other"}]},
        }],
    }
    assert iteration_video._runtime_attached_values(run, [], "evidence") == []


def test_generated_runtime_run_without_parent_fields_is_incomplete() -> None:
    record = iteration_video._normalize_runtime_record(
        {"run_id": TARGET_RUN_ID, "project_id": "demo"}, client=object(), project="demo"
    )
    assert "parent_run_ids" not in record
    assert "provenance" not in record
    assert record["runtime_parent_lineage_available"] is False

    node = iteration_video.RuntimeRunNode(
        run_id=TARGET_RUN_ID,
        record=record,
        depth=0,
        label="target",
    )
    _manifest, quality = iteration_video._build_runtime_inputs(
        [node], target_run_id=TARGET_RUN_ID, project_slug="demo"
    )
    assert quality["data_quality"] < 1.0
    assert quality["missing_lineage"] == [TARGET_RUN_ID]
    assert "lineage_unavailable" in quality["unavailable_sources"]


def test_iteration_malformed_parent_ids_remain_missing_lineage() -> None:
    record = iteration_video._normalize_runtime_record(
        {"run_id": TARGET_RUN_ID, "project_id": "demo", "parent_run_ids": [None]},
        client=object(),
        project="demo",
    )
    assert record["runtime_parent_lineage_available"] is False
    node = iteration_video.RuntimeRunNode(
        run_id=TARGET_RUN_ID, record=record, depth=0, label="target"
    )
    _manifest, quality = iteration_video._build_runtime_inputs(
        [node], target_run_id=TARGET_RUN_ID, project_slug="demo"
    )
    assert quality["missing_lineage"] == [TARGET_RUN_ID]
    assert quality["dimensions"]["lineage"] is False
    _edges, unresolved = iteration_video._runtime_parent_edges(record, {})
    assert unresolved == ["invalid_parent_lineage"]
    graph = iteration_video._collect_runtime_graph({TARGET_RUN_ID: record}, TARGET_RUN_ID)
    assert graph[0].lineage_incomplete is True


def test_iteration_video_public_route_materializes_runtime_output_object(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("banodoco_timeline_schema")
    payload = b"runtime-owned image bytes"
    digest = hashlib.sha256(payload).hexdigest()

    class Runtime:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []
            self.objects: list[tuple[str, str]] = []
            self.runs = self
            self.media = self

        def list(self, project: str):
            self.calls.append(("list", project))
            return SimpleNamespace(ok=True, data=[{
                "run_id": TARGET_RUN_ID,
                "status": "succeeded",
                "output_artifacts": [{
                    "kind": "image",
                    "object_id": "object-image-1",
                    "digest": f"sha256:{digest}",
                    "size": len(payload),
                    "media_type": "image/png",
                }],
            }])

        def show(self, project: str, object_id: str):
            self.objects.append((project, object_id))
            return SimpleNamespace(data=payload)

    runtime = Runtime()
    out_dir = tmp_path / "iteration-video"

    def fake_render(timeline: Path, assets: Path, output: Path, **_kwargs) -> Path:
        assert json.loads(timeline.read_text(encoding="utf-8"))["clips"][0]["clipType"] == "media"
        asset = next(iter(json.loads(assets.read_text(encoding="utf-8"))["assets"].values()))
        assert Path(asset["file"]).read_bytes() == payload
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"rendered-mp4")
        Path(f"{output}.provenance.json").write_text("{}\n", encoding="utf-8")
        return output

    monkeypatch.setattr(iteration_video, "_runtime_client_context", lambda *_args: nullcontext(runtime))
    monkeypatch.setattr(iteration_video, "invoke_attached_render", fake_render)

    result = run_orchestrator(
        OrchestratorRunRequest(
            orchestrator_id="video_editing.iteration_video",
            out=out_dir,
            project="demo",
            project_was_auto_resolved=True,
            run_root=None,
            inputs={"target_run_id": TARGET_RUN_ID},
            orchestrator_args=("--repo-root", str(tmp_path), "--renderer", "rendering.fixture"),
        )
    )

    assert result.ok
    assert runtime.calls == [("list", "demo")]
    assert runtime.objects == [("demo", "object-image-1")]
    assert (out_dir / "iteration.mp4").read_bytes() == b"rendered-mp4"
    assert _read_json(out_dir / "iteration.quality.json")["data_quality"] < 1.0
    assert not (out_dir / "run.json").exists()


def test_iteration_video_orchestrator_declares_no_cut_child() -> None:
    manifest = _read_json(Path("astrid/packs/video_editing/orchestrators/iteration_video/orchestrator.yaml"))
    assert manifest["child_executors"] == ["iteration.assemble", "rendering.render"]
    assert "video_editing.cut" not in manifest["child_executors"]
    assert {item["name"] for item in manifest["outputs"]} == {
        "iteration.mp4",
        "iteration.mp4.provenance.json",
    }


def test_iteration_plan_uses_qualified_facade_and_declares_provenance(tmp_path: Path) -> None:
    plan = plan_template.build_plan_v2(
        python_exec="python3",
        run_root=tmp_path / "run",
        target_run_id=TARGET_RUN_ID,
        renderer="rendering.fixture",
    )

    render = plan["steps"][2]
    assert "-m astrid executors run rendering.render" in render["command"]
    assert "output_name=iteration.mp4" in render["command"]
    assert "engine=rendering.fixture" in render["command"]
    assert "astrid.packs.rendering.executors.render.run" not in render["command"]
    assert {item["path"] for item in render["produces"].values()} == {
        "iteration.mp4",
        "iteration.mp4.provenance.json",
    }


def _runtime_client(*, include_root: bool = False):
    records = [_record(TARGET_RUN_ID, output_artifacts=[_artifact("image", "b" * 64), _artifact("model_3d", "c" * 64)])]
    if include_root:
        records.insert(0, _record(ROOT_RUN_ID, output_artifacts=[_artifact("image", "a" * 64)]))
        records[1]["parent_run_ids"] = [{"run_id": ROOT_RUN_ID, "kind": "causal"}]

    calls: list[tuple[str, str]] = []

    class Runs:
        def list(self, project):
            calls.append(("list", project))
            return type("Result", (), {"ok": True, "data": records})()

        def events(self, project, run_id):
            return [{"event_id": f"event-{run_id}", "aggregate_id": run_id, "event_type": "run.completed", "payload": {"evidence": [{"id": f"e-{run_id}"}], "receipt": {"id": f"r-{run_id}"}}}]

    class Tasks:
        def list(self, project):
            return type("Result", (), {"ok": True, "data": [{
                "task_id": f"task-{TARGET_RUN_ID}", "run_id": TARGET_RUN_ID,
                "project_id": project,
                "output_artifacts": [_artifact("image", "d" * 64)],
            }]})()

        def events(self, task_id, project=None):
            return [{"event_id": f"event-{task_id}", "aggregate_id": task_id, "event_type": "task.completed", "payload": {}}]

    class Media:
        def list_relations(self, project):
            return [{"from_run_id": TARGET_RUN_ID, "to_run_id": ROOT_RUN_ID, "kind": "derived_from"}]

    runtime = type("Runtime", (), {"runs": Runs(), "tasks": Tasks(), "media": Media()})()
    runtime.calls = calls
    return runtime


def _record(
    run_id: str,
    *,
    parent_run_ids: list[dict] | None = None,
    output_artifacts: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "project_id": "demo",
        "parent_run_ids": parent_run_ids or [],
        "executor_id": "generation.generate_image_openai",
        "orchestrator_id": None,
        "kind": "executor",
        "status": "succeeded",
        "returncode": 0,
        "out_path": f"runs/{run_id}",
        "brief_content_sha256": "e" * 64,
        "input_artifacts": [],
        "output_artifacts": output_artifacts or [],
        "provenance": {"contributing_runs": []},
    }


def _artifact(kind: str, sha: str) -> dict:
    return {"kind": kind, "role": "other", "sha256": sha, "path": f"runs/artifact-{sha[:8]}.dat"}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
