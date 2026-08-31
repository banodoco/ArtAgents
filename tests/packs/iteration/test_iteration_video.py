import contextlib
import io
import json
from contextlib import nullcontext
from pathlib import Path

from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator
from astrid.packs.video_editing.orchestrators.iteration_video import plan_template
from astrid.packs.video_editing.orchestrators.iteration_video import run as iteration_video

THREAD_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV0"
TARGET_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV1"
ROOT_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV2"


def test_iteration_video_public_route_uses_runtime_authority(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path
    out_dir = repo / "runs" / "iteration-video"
    forwarded: dict[str, object] = {}
    runtime = _runtime_client()

    def fake_assemble_iteration(**kwargs):
        forwarded["input_manifest"] = kwargs["input_manifest"]
        out = kwargs["out_path"]
        out.mkdir(parents=True, exist_ok=True)
        _write_json(out / "iteration.manifest.json", {"runs": [], "quality": {"data_quality": 1.0}})
        _write_json(out / "iteration.quality.json", {"data_quality": 1.0})
        _write_json(out / "hype.timeline.json", {})
        _write_json(out / "hype.assets.json", {})
        return {"manifest_path": str(out / "iteration.manifest.json")}

    def fake_render(timeline: Path, assets: Path, output: Path, **kwargs) -> Path:
        forwarded["render_timeline"] = timeline
        forwarded["render_assets"] = assets
        forwarded["render_output"] = output
        forwarded["render_kwargs"] = kwargs
        assert timeline.is_file()
        assert assets.is_file()
        output.write_bytes(b"rendered-mp4")
        Path(f"{output}.provenance.json").write_text(
            json.dumps({"output": str(output)}) + "\n",
            encoding="utf-8",
        )
        return output

    monkeypatch.setattr(iteration_video, "_runtime_client_context", lambda *_args: nullcontext(runtime))
    monkeypatch.setattr(iteration_video.assemble, "assemble_iteration", fake_assemble_iteration)
    monkeypatch.setattr(iteration_video, "invoke_attached_render", fake_render)

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        result = run_orchestrator(
            OrchestratorRunRequest(
                orchestrator_id="video_editing.iteration_video",
                out=out_dir,
                project="demo",
                project_was_auto_resolved=True,
                run_root=out_dir,
                execution_mode="in_process",
                inputs={"thread": THREAD_ID, "target_run_id": TARGET_RUN_ID},
                orchestrator_args=(
                    "--repo-root",
                    str(repo),
                    "--max-iterations",
                    "7",
                    "--direction",
                    "label only",
                    "--clip-mode",
                    "hold",
                    "--renderer",
                    "rendering.fixture",
                ),
            )
        )

    assert result.ok
    assert runtime.calls == [("list", "demo")]
    assert forwarded["input_manifest"]["authority"] == {"kind": "runtime", "project": "demo", "run_ids": [TARGET_RUN_ID]}
    assert Path(forwarded["render_timeline"]).name == "hype.timeline.json"
    assert Path(forwarded["render_assets"]).name == "hype.assets.json"
    assert Path(forwarded["render_output"]).name == "iteration.mp4"
    render_kwargs = forwarded["render_kwargs"]
    assert render_kwargs["engine"] == "rendering.fixture"
    assert render_kwargs["project_slug"] == "demo"
    assert render_kwargs["parent_run_id"] == out_dir.name
    assert render_kwargs["step_id"] == "iteration-render"
    assert (out_dir / "iteration.mp4").read_bytes() == b"rendered-mp4"
    assert _read_json(out_dir / "iteration.mp4.provenance.json")["output"] == str(
        out_dir / "iteration.mp4"
    )
    assert not (out_dir / "hype.mp4").exists()
    assert not (out_dir / "hype.mp4.provenance.json").exists()
    assert not (out_dir / "_prepare").exists()

    assert not (out_dir / "run.json").exists()
    assert not (out_dir / ".astrid.variants.json").exists()
    assert not (repo / ".astrid" / "threads" / THREAD_ID / "groups.json").exists()


def test_iteration_video_inspect_does_not_render_or_summarize_and_suppresses_content(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    runtime = _runtime_client(include_root=True)

    def fail_render(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("inspect must not render")

    monkeypatch.setattr(iteration_video, "_runtime_client_context", lambda *_args: nullcontext(runtime))
    monkeypatch.setattr(iteration_video, "run_builtin_render", fail_render)

    report = iteration_video.inspect_iteration_thread(repo_root=repo, thread_ref=THREAD_ID, target_run_id=TARGET_RUN_ID, project_slug="demo")
    text = iteration_video.format_inspection(report, no_content=True)

    assert report["summary_cache"] == {"hits": 0, "misses": 0}
    assert report["detected_modalities"] == ["image", "model_3d"]
    assert {item["renderer"] for item in report["chosen_renderers"]} == {"image_grid", "generic_card"}
    assert "Estimated cost: ~$0.000" in text
    assert "content: suppressed" in text
    assert "SECRET prompt" not in text


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

    runtime = type("Runtime", (), {"runs": Runs()})()
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
        "thread_id": THREAD_ID,
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
