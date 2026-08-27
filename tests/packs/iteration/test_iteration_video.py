import contextlib
import io
import json
from pathlib import Path

from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator
from astrid.core.project.project import create_project
from astrid.core.threads.index import ThreadIndexStore
from astrid.core.threads.schema import make_thread_record
from astrid.packs.video_editing.orchestrators.iteration_video import plan_template
from astrid.packs.video_editing.orchestrators.iteration_video import run as iteration_video

THREAD_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV0"
TARGET_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV1"
ROOT_RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FV2"


def test_iteration_video_renders_attached_and_records_six_output_variant_group(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path
    projects_root = repo / "projects"
    out_dir = repo / "runs" / "iteration-video"
    forwarded: dict[str, object] = {}
    _write_thread(repo)

    def fake_prepare_iteration(**kwargs):
        forwarded["max_iterations"] = kwargs["max_iterations"]
        _write_prepare_outputs(kwargs["out_path"])
        return {"manifest_path": str(kwargs["out_path"] / "iteration.manifest.json")}

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

    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    create_project("demo", root=projects_root)
    monkeypatch.setattr(iteration_video.prepare, "prepare_iteration", fake_prepare_iteration)
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
    assert forwarded["max_iterations"] == 7
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
    run_records = sorted((projects_root / "demo" / "runs").glob("*/run.json"))
    assert run_records == []
    sidecar = _read_json(out_dir / ".astrid.variants.json")
    variant_artifacts = [artifact for artifact in sidecar["artifacts"] if artifact.get("role") == "variant"]
    assert sorted(Path(item["path"]).name for item in variant_artifacts) == [
        "iteration.manifest.json",
        "iteration.mp4",
        "iteration.mp4.provenance.json",
        "iteration.quality.json",
        "iteration.report.html",
        "iteration.timeline.json",
    ]
    assert {item["group"] for item in variant_artifacts} == {f"iteration-video:{TARGET_RUN_ID}"}
    assert all(item["variant_meta"]["target_run_id"] == TARGET_RUN_ID for item in variant_artifacts)

    groups = _read_json(repo / ".astrid" / "threads" / THREAD_ID / "groups.json")
    group = groups["groups"][f"iteration-video:{TARGET_RUN_ID}"]
    assert len(group["artifacts"]) == 6
    assert {item["run_id"] for item in group["artifacts"]} == {TARGET_RUN_ID}


def test_iteration_video_inspect_does_not_render_or_summarize_and_suppresses_content(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _write_thread(repo)
    _write_run(
        repo,
        "root",
        _record(ROOT_RUN_ID, output_artifacts=[_artifact("image", "a" * 64)]),
    )
    _write_run(
        repo,
        "target",
        _record(
            TARGET_RUN_ID,
            parent_run_ids=[{"run_id": ROOT_RUN_ID, "kind": "causal"}],
            output_artifacts=[
                _artifact("image", "b" * 64),
                _artifact("model_3d", "c" * 64),
            ],
        ),
    )
    cache_dir = repo / ".astrid" / "iteration_cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / f"{ROOT_RUN_ID}__understanding.understand.v1.json").write_text("{}\n", encoding="utf-8")

    def fail_prepare(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("inspect must not summarize")

    def fail_render(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("inspect must not render")

    monkeypatch.setattr(iteration_video.prepare, "prepare_iteration", fail_prepare)
    monkeypatch.setattr(iteration_video, "run_builtin_render", fail_render)

    report = iteration_video.inspect_iteration_thread(repo_root=repo, thread_ref=THREAD_ID, target_run_id=TARGET_RUN_ID)
    text = iteration_video.format_inspection(report, no_content=True)

    assert report["summary_cache"] == {"hits": 1, "misses": 1}
    assert report["detected_modalities"] == ["image", "model_3d"]
    assert {item["renderer"] for item in report["chosen_renderers"]} == {"image_grid", "generic_card"}
    assert "Estimated cost: ~$0.009" in text
    assert "content: suppressed" in text
    assert "SECRET prompt" not in text


def test_iteration_video_orchestrator_declares_no_cut_child() -> None:
    manifest = _read_json(Path("astrid/packs/video_editing/orchestrators/iteration_video/orchestrator.yaml"))
    assert manifest["child_executors"] == ["iteration.prepare", "iteration.assemble", "rendering.render"]
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


def _write_thread(repo: Path) -> None:
    thread = make_thread_record(thread_id=THREAD_ID, label="Logo Sprint")
    thread["run_ids"] = [ROOT_RUN_ID, TARGET_RUN_ID]
    ThreadIndexStore(repo).write({"schema_version": 1, "active_thread_id": THREAD_ID, "threads": {THREAD_ID: thread}})


def _write_prepare_outputs(out_path: Path) -> None:
    out_path.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "target_run_id": TARGET_RUN_ID,
        "thread_id": THREAD_ID,
        "runs": [
            {
                "run_id": TARGET_RUN_ID,
                "thread_id": THREAD_ID,
                "label": "in_thread",
                "causal_depth": 0,
                "output_artifacts": [
                    {"kind": "image", "role": "other", "path": "runs/source/image.png", "sha256": "a" * 64, "duration": 4}
                ],
                "summary": {"summary": "SECRET prompt should not appear in no-content output"},
            }
        ],
        "quality": {"data_quality": 0.95},
    }
    quality = {
        "schema_version": 1,
        "target_run_id": TARGET_RUN_ID,
        "data_quality": 0.95,
        "valid_roots": [TARGET_RUN_ID],
        "unresolved_producer_runs": [],
    }
    _write_json(out_path / "iteration.manifest.json", manifest)
    _write_json(out_path / "iteration.quality.json", quality)


def _write_run(repo: Path, slug: str, record: dict) -> None:
    run_dir = repo / "runs" / slug
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "run.json", record)


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
