from __future__ import annotations

import json
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

from astrid.core.contracts.run_status import RunStatus
from astrid.core.contracts.schema import CommandSpec, Port
from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.runner import ExecutorRunnerError, ExecutorRunRequest, run_executor
from astrid.core.execution.executor.schema import ConditionSpec, ExecutorDefinition
from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.core.foundation import project_paths as paths
from astrid.core.project.project import create_project
from astrid.core.project.run import resolve_record_path
from astrid.core.timeline.crud import create_timeline
from astrid.packs.video_editing.orchestrators.hype import run as hype


def test_executor_project_runs_finalize_success_error_skip_and_avoid_thread_collision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    projects_root = repo / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)
    registry = ExecutorRegistry([_writer_executor("test.writer"), _requires_executor("test.requires"), _skip_executor("test.skip")])

    success = run_executor(ExecutorRunRequest("test.writer", out="", project="demo"), registry)
    with pytest.raises(ExecutorRunnerError, match="missing required input") as excinfo:
        run_executor(ExecutorRunRequest("test.requires", out="", project="demo"), registry)
    skipped = run_executor(ExecutorRunRequest("test.skip", out="", project="demo", inputs={"skip_me": "1"}), registry)

    assert success.returncode == 0
    assert skipped.skipped is True
    records = _project_records(projects_root)
    assert [record["status"] for record in records] == ["completed", "failed", "skipped"]
    assert records[1]["metadata"]["returncode"] == -1
    assert records[1]["metadata"]["error"] == str(excinfo.value)
    writer_out = resolve_record_path(records[0]["out"], records[0]["project_slug"])
    assert (writer_out / "env.txt").read_text(encoding="utf-8") == "1"
    assert (writer_out / "run.json").exists()
    assert not (repo / ".astrid" / "threads.json").exists()


def test_executor_legacy_out_no_longer_writes_thread_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    projects_root = tmp_path / "projects"
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("default")
    create_timeline("default", "main", is_default=True)
    registry = ExecutorRegistry([_writer_executor("test.writer")])
    out = repo / "runs" / "legacy"

    result = run_executor(ExecutorRunRequest("test.writer", out=out), registry)

    assert result.returncode == 0
    assert not (out / "run.json").exists()
    assert not (repo / ".astrid" / "threads.json").exists()
    records = [_read_json(path) for path in sorted((projects_root / "default" / "runs").glob("*/run.json"))]
    assert [record["project_slug"] for record in records] == ["default"]
    assert records[0]["out"] == str(out)
    assert records[0]["metadata"]["project_was_auto_resolved"] is True
    assert (Path(records[0]["out"]) / "env.txt").read_text(encoding="utf-8") == "1"


def test_orchestrator_project_run_injects_hype_out_and_command_runtime_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)
    registry = OrchestratorRegistry([_writer_orchestrator("test.orch")])

    result = run_orchestrator(OrchestratorRunRequest("test.orch", project="demo"), registry)

    assert result.returncode == 0
    record = _project_records(projects_root)[0]
    assert record["status"] == "completed"
    assert record["tool_id"] == "test.orch"
    assert (resolve_record_path(record["out"], record["project_slug"]) / "orch-env.txt").read_text(encoding="utf-8") == "1"

    hype_registry = OrchestratorRegistry([_hype_command_orchestrator()])
    dry = run_orchestrator(
        OrchestratorRunRequest(
            "video_editing.hype",
            project="demo",
            dry_run=True,
            orchestrator_args=("--brief", str(tmp_path / "brief.txt"), "--target-duration", "1"),
        ),
        hype_registry,
    )
    assert dry.dry_run is True
    assert "--out" in dry.command
    assert str((Path.cwd() / ".astrid-dry-run" / "video_editing-hype").resolve()) in " ".join(dry.command)
    assert len(_project_records(projects_root)) == 1


def test_orchestrator_out_only_auto_resolves_default_project_and_ledgers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    monkeypatch.setenv("ASTRID_SESSION_ID", "S-ORCH-OUT")
    _clear_thread_env(monkeypatch)
    create_project("default")
    create_timeline("default", "main", is_default=True)

    out_dir = tmp_path / "orch-out"
    registry = OrchestratorRegistry([_writer_orchestrator("test.orch")])

    result = run_orchestrator(OrchestratorRunRequest("test.orch", out=out_dir), registry)

    assert result.returncode == 0
    records = [_read_json(path) for path in sorted((projects_root / "default" / "runs").glob("*/run.json"))]
    assert len(records) == 1
    assert records[0]["project_slug"] == "default"
    assert records[0]["out"] == str(out_dir.resolve())
    assert records[0]["session_id"] == "S-ORCH-OUT"
    assert records[0]["auto_bound"] is True
    assert records[0]["invocation"] == "cli"
    assert records[0]["metadata"]["project_was_auto_resolved"] is True
    assert (out_dir / "orch-env.txt").read_text(encoding="utf-8") == "1"


def test_direct_hype_project_validation_error_and_nested_artifact_mirroring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)

    code = hype.main(["--project", "demo", "--target-duration", "1"])
    assert code == 2
    error_record = _project_records(projects_root)[0]
    assert error_record["status"] == "failed"
    assert error_record["metadata"]["returncode"] == 2

    brief = tmp_path / "brief.txt"
    brief.write_text("make a short thing", encoding="utf-8")

    def fake_pool(args):
        args.brief_out.mkdir(parents=True, exist_ok=True)
        (args.brief_out / "hype.timeline.json").write_text(json.dumps({"theme": "banodoco-default", "clips": []}), encoding="utf-8")
        (args.brief_out / "hype.assets.json").write_text(json.dumps({"assets": {}}), encoding="utf-8")
        (args.brief_out / "hype.metadata.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        return 0

    monkeypatch.setattr(hype, "pool_main", fake_pool)
    code = hype.main(["--project", "demo", "--brief", str(brief), "--target-duration", "1", "--brief-slug", "brief-a"])
    assert code == 0
    success_record = _project_records(projects_root)[1]
    assert success_record["status"] == "completed"
    assert sorted(success_record["artifacts"]) == ["assets", "metadata", "timeline"]
    assert success_record["artifacts"]["timeline"]["source_path"].endswith("briefs/brief-a/hype.timeline.json")
    assert not Path(success_record["artifacts"]["timeline"]["path"]).is_absolute()
    assert (resolve_record_path(success_record["out"], success_record["project_slug"]) / "timeline.json").exists()


def test_project_run_rejects_project_plus_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    registry = ExecutorRegistry([_writer_executor("test.writer")])

    with pytest.raises(Exception, match="--project cannot be combined with --out"):
        run_executor(ExecutorRunRequest("test.writer", out=tmp_path / "out", project="demo"), registry)
    assert list((tmp_path / "projects" / "demo" / "runs").glob("*")) == []


def test_project_run_allows_implicit_out_when_project_supplied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    projects_root = tmp_path / "projects"
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)
    registry = ExecutorRegistry([_writer_executor("test.writer")])

    result = run_executor(ExecutorRunRequest("test.writer", out=None, project="demo"), registry)

    assert result.returncode == 0
    records = _project_records(projects_root)
    assert [record["status"] for record in records] == ["completed"]
    writer_out = resolve_record_path(records[0]["out"], records[0]["project_slug"])
    assert writer_out.exists()
    assert (writer_out / "env.txt").read_text(encoding="utf-8") == "1"


def test_prepare_project_run_skips_timeline_when_requires_timeline_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stateless run (requires_timeline=False) prepares with no live
    timeline and writes a run record carrying no timeline_id."""
    from astrid.core.project.run import prepare_project_run

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")  # NB: no create_timeline() — there is no live timeline.

    context = prepare_project_run(
        "demo",
        tool_id="test.stateless",
        kind="executor",
        requires_timeline=False,
    )

    assert "timeline_id" not in context.record
    assert (
        resolve_record_path(context.record["out"], context.project_slug, root=projects_root) / "run.json"
    ).exists() or context.run_json_path.exists()
    on_disk = _read_json(context.run_json_path)
    assert "timeline_id" not in on_disk


def test_prepare_project_run_demands_timeline_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default (requires_timeline left unset → True) still demands a live
    timeline, preserving backward-compatible behavior for timeline-aware
    executors."""
    from astrid.core.project.run import ProjectRunError, prepare_project_run

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")  # no timeline

    with pytest.raises(ProjectRunError, match="no live timelines"):
        prepare_project_run("demo", tool_id="test.stateful", kind="executor")


def test_executor_runner_resolves_requires_timeline_from_executor_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The executor runner resolves ``metadata.requires_timeline`` from the
    ExecutorDefinition it already holds and passes the concrete flag into
    prepare_project_run, so a stateless executor (requires_timeline=False) runs
    cleanly against a project with no live timeline — without the project tier
    reaching back up into the executor registry."""
    repo = tmp_path / "repo"
    repo.mkdir()
    projects_root = repo / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    _clear_thread_env(monkeypatch)
    create_project("demo")  # NB: no create_timeline()

    stateless = ExecutorDefinition(
        id="test.stateless_optout",
        name="Stateless",
        kind="external",
        version="1.0",
        command=CommandSpec(argv=(sys.executable, "-c", "pass")),
        metadata={"requires_timeline": False},
    )
    # Resolving requires_timeline=False from metadata lets prepare_project_run
    # skip the "no live timelines" demand that would otherwise raise.
    result = run_executor(
        ExecutorRunRequest("test.stateless_optout", out="", project="demo"),
        ExecutorRegistry([stateless]),
    )
    assert result.returncode == 0

    run_jsons = list((projects_root / "demo" / "runs").glob("*/run.json"))
    assert len(run_jsons) == 1
    assert "timeline_id" not in _read_json(run_jsons[0])


def test_prepare_project_run_records_external_out_and_prepare_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.project.run import prepare_project_run

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)

    external_out = tmp_path / "external-output"
    context = prepare_project_run(
        "demo",
        tool_id="test.writer",
        kind="executor",
        record_out=external_out,
    )

    assert context.run_root != external_out.resolve()
    assert context.record["out"] == str(external_out)
    metadata = context.record["metadata"]
    assert metadata["pid"] > 0
    assert metadata["prepared_at"]
    assert metadata["process_platform"] == sys.platform
    on_disk = _read_json(context.run_json_path)
    assert on_disk["out"] == str(external_out)
    assert on_disk["metadata"]["process_platform"] == sys.platform


def test_standalone_timeline_contribution_records_only_after_successful_finalize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.project.run import finalize_project_run, prepare_project_run

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    timeline = create_timeline("demo", "main", is_default=True)
    manifest_path = projects_root / "demo" / "timelines" / timeline["ulid"] / "manifest.json"

    context = prepare_project_run("demo", tool_id="test.writer", kind="executor")

    assert _read_json(manifest_path)["contributing_runs"] == []

    finalize_project_run(context, status=RunStatus.COMPLETED, returncode=0)

    assert _read_json(manifest_path)["contributing_runs"] == [context.run_id]


def test_failed_standalone_timeline_run_does_not_record_contribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.project.run import finalize_project_run, prepare_project_run

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    timeline = create_timeline("demo", "main", is_default=True)
    manifest_path = projects_root / "demo" / "timelines" / timeline["ulid"] / "manifest.json"

    context = prepare_project_run("demo", tool_id="test.writer", kind="executor")
    finalize_project_run(context, status=RunStatus.FAILED, returncode=1)

    assert _read_json(manifest_path)["contributing_runs"] == []


def test_task_attached_parent_contribution_remains_prepare_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.project.run import prepare_project_run, write_run_record
    from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    timeline = create_timeline("demo", "main", is_default=True)
    parent_run_id = "01ARZ3NDEKTSV4RRFFQ69G5FAT"
    write_run_record(
        "demo",
        parent_run_id,
        kind="task",
        status=RunStatus.RUNNING,
        timeline_id=timeline["ulid"],
    )
    monkeypatch.setenv(TASK_PROJECT_ENV, "demo")
    monkeypatch.setenv(TASK_RUN_ID_ENV, parent_run_id)
    monkeypatch.setenv(TASK_STEP_ID_ENV, "render")
    manifest_path = projects_root / "demo" / "timelines" / timeline["ulid"] / "manifest.json"

    context = prepare_project_run("demo", tool_id="test.writer", kind="executor")

    assert context.run_id == parent_run_id
    assert _read_json(manifest_path)["contributing_runs"] == [parent_run_id]


def test_concurrent_successful_finalizes_do_not_lose_timeline_contributions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.project.run import finalize_project_run, prepare_project_run
    from astrid.core.timeline import crud as timeline_crud

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    timeline = create_timeline("demo", "main", is_default=True)
    manifest_path = projects_root / "demo" / "timelines" / timeline["ulid"] / "manifest.json"
    contexts = [
        prepare_project_run("demo", tool_id="test.writer", kind="executor"),
        prepare_project_run("demo", tool_id="test.writer", kind="executor"),
    ]

    original_manifest_lock = timeline_crud._manifest_lock
    first_thread_holds_lock = threading.Event()
    second_thread_attempted_lock = threading.Event()
    entrant_state = {"count": 0}
    state_lock = threading.Lock()

    @contextmanager
    def coordinated_manifest_lock(path: Path):
        with state_lock:
            entrant_state["count"] += 1
            entrant_number = entrant_state["count"]
        if entrant_number == 1:
            with original_manifest_lock(path):
                first_thread_holds_lock.set()
                assert second_thread_attempted_lock.wait(timeout=2), "second finalize never contended for the manifest lock"
                yield
            return
        second_thread_attempted_lock.set()
        with original_manifest_lock(path):
            yield

    monkeypatch.setattr(timeline_crud, "_manifest_lock", coordinated_manifest_lock)

    thread_errors: list[BaseException] = []

    def finalize(context) -> None:
        try:
            finalize_project_run(context, status=RunStatus.COMPLETED, returncode=0)
        except BaseException as exc:  # pragma: no cover - surfaced through assertion below.
            thread_errors.append(exc)

    first = threading.Thread(target=finalize, args=(contexts[0],))
    second = threading.Thread(target=finalize, args=(contexts[1],))
    first.start()
    assert first_thread_holds_lock.wait(timeout=2), "first finalize never acquired the manifest lock"
    second.start()
    first.join()
    second.join()

    assert thread_errors == []
    assert second_thread_attempted_lock.is_set()
    assert _read_json(manifest_path)["contributing_runs"] == [context.run_id for context in contexts]


def test_run_record_baseline_snapshot_is_sha256_hex_at_canonical_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SD-008: baseline_snapshot is a sha256 hex string at exactly
    runs/<run_id>.json#metadata.baseline_snapshot."""

    import hashlib

    from astrid.core.project.run import write_run_record

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    create_project("demo")

    snapshot_payload = {"theme": "banodoco-default", "clips": []}
    canonical = json.dumps(snapshot_payload, sort_keys=True, separators=(",", ":"))
    expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    record = write_run_record(
        "demo",
        "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        tool_id="astrid.core.integrations.worker.banodoco_worker",
        kind="banodoco_timeline_generate",
        metadata={"baseline_snapshot": expected_digest},
    )

    digest = record["metadata"]["baseline_snapshot"]
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)
    assert digest == expected_digest

    run_json_path = (
        projects_root / "demo" / "runs" / "01ARZ3NDEKTSV4RRFFQ69G5FAV" / "run.json"
    )
    assert run_json_path.is_file()
    on_disk = json.loads(run_json_path.read_text(encoding="utf-8"))
    assert on_disk["metadata"]["baseline_snapshot"] == expected_digest


def test_load_run_record_normalizes_legacy_status_without_rewriting_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.project.run import load_run_record

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    create_project("demo")
    legacy_path = projects_root / "demo" / "runs" / "01ARZ3NDEKTSV4RRFFQ69G5FAV" / "run.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_payload = {
        "artifacts": {},
        "created_at": "2026-06-01T00:00:00Z",
        "metadata": {},
        "out": str(legacy_path.parent),
        "project_slug": "demo",
        "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "schema_version": 1,
        "status": "prepared",
        "updated_at": "2026-06-01T00:00:00Z",
    }
    encoded = json.dumps(legacy_payload, indent=2, sort_keys=True) + "\n"
    legacy_path.write_text(encoded, encoding="utf-8")

    loaded = load_run_record("demo", "01ARZ3NDEKTSV4RRFFQ69G5FAV")

    assert loaded["status"] == RunStatus.RUNNING.value
    assert legacy_path.read_text(encoding="utf-8") == encoded
    assert resolve_record_path(loaded["out"], "demo") == legacy_path.parent.resolve()


def test_project_internal_record_paths_are_stored_project_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.project.run import finalize_project_run, prepare_project_run

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)

    context = prepare_project_run("demo", tool_id="test.writer", kind="executor")
    run_out = resolve_record_path(context.record["out"], context.project_slug, root=projects_root)
    (run_out / "manifest.json").write_text(
        json.dumps({"outputs": [{"path": "image_001.png", "type": "image/png"}]}),
        encoding="utf-8",
    )
    (run_out / "hype.timeline.json").write_text(json.dumps({"clips": []}), encoding="utf-8")
    (run_out / "hype.assets.json").write_text(json.dumps({"assets": {}}), encoding="utf-8")
    (run_out / "hype.metadata.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    finalize_project_run(context, status=RunStatus.COMPLETED, returncode=0)

    on_disk = _read_json(context.run_json_path)
    assert on_disk["out"] == f"runs/{context.run_id}"
    assert on_disk["manifest_path"] == f"runs/{context.run_id}/manifest.json"
    for artifact in on_disk["artifacts"].values():
        assert not Path(artifact["path"]).is_absolute()
        assert not Path(artifact["source_path"]).is_absolute()
        assert resolve_record_path(artifact["path"], "demo").exists()


def _writer_executor(executor_id: str) -> ExecutorDefinition:
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "out = Path(sys.argv[1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'env.txt').write_text(os.environ.get('ASTRID_PROJECT_RUN', ''), encoding='utf-8')\n"
    )
    return ExecutorDefinition(
        id=executor_id,
        name="Writer",
        kind="external",
        version="1.0",
        command=CommandSpec(argv=(sys.executable, "-c", script, "{out}")),
    )


def _requires_executor(executor_id: str) -> ExecutorDefinition:
    return ExecutorDefinition(
        id=executor_id,
        name="Requires",
        kind="external",
        version="1.0",
        inputs=(Port(name="needed", type="string", required=True),),
        command=CommandSpec(argv=(sys.executable, "-c", "print('unused')")),
    )


def _skip_executor(executor_id: str) -> ExecutorDefinition:
    return ExecutorDefinition(
        id=executor_id,
        name="Skip",
        kind="external",
        version="1.0",
        inputs=(Port(name="skip_me", type="string", required=False),),
        conditions=(ConditionSpec(kind="skip_if_input", input="skip_me"),),
        command=CommandSpec(argv=(sys.executable, "-c", "print('unused')")),
    )


def _writer_orchestrator(orchestrator_id: str) -> OrchestratorDefinition:
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "out = Path(sys.argv[1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'orch-env.txt').write_text(os.environ.get('ASTRID_PROJECT_RUN', ''), encoding='utf-8')\n"
    )
    return OrchestratorDefinition(
        id=orchestrator_id,
        name="Orchestrator",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(kind="command", command=CommandSpec(argv=(sys.executable, "-c", script, "{out}"))),
    )


def _hype_command_orchestrator() -> OrchestratorDefinition:
    return OrchestratorDefinition(
        id="video_editing.hype",
        name="Hype",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(
            kind="command",
            command=CommandSpec(argv=(sys.executable, "-m", "astrid.packs.video_editing.orchestrators.hype.run", "{orchestrator_args}")),
        ),
        metadata={"requires_output_path": True},
    )


def _project_records(projects_root: Path) -> list[dict]:
    return [_read_json(path) for path in sorted((projects_root / "demo" / "runs").glob("*/run.json"))]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _clear_thread_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ASTRID_THREADS_OFF",
        "ASTRID_THREAD_INHERITED",
        "ASTRID_THREAD_ID",
        "ASTRID_RUN_ID",
        "ASTRID_PARENT_RUN_ID",
        "ASTRID_PROJECT_RUN",
        "ASTRID_TASK_RUN_ID",
        "ASTRID_TASK_PROJECT",
        "ASTRID_TASK_STEP_ID",
        "ASTRID_TASK_ITEM_ID",
        "ASTRID_TASK_ITERATION",
    ):
        monkeypatch.delenv(name, raising=False)


# ── m3.5 T18: Managed hype preparation tests ────────────────────────────


def test_hype_prepare_project_main_writes_ulid_to_timeline_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove _prepare_project_main writes a valid ULID to run.timeline_id."""
    from astrid.packs.video_editing.orchestrators.hype.run import _prepare_project_main
    from astrid.core.threads.ids import is_ulid

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    brief = tmp_path / "brief.txt"
    brief.write_text("make a short thing", encoding="utf-8")

    context, effective_argv = _prepare_project_main(
        ["--project", "demo", "--brief", str(brief), "--brief-slug", "brief-a"]
    )

    assert context is not None
    timeline_id = context.record.get("timeline_id")
    assert timeline_id is not None, "run.timeline_id must be set for managed runs"
    assert is_ulid(timeline_id), (
        f"run.timeline_id must be a valid ULID, got {timeline_id!r}"
    )


def test_hype_prepare_project_main_writes_slug_and_uuid_to_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove _prepare_project_main writes timeline_slug and timeline_event_stream_id to run.metadata."""
    import uuid as _uuid

    from astrid.core.project.run import (
        METADATA_KEY_TIMELINE_BINDING_MODE,
        METADATA_KEY_TIMELINE_EVENT_STREAM_ID,
        METADATA_KEY_TIMELINE_SLUG,
    )
    from astrid.packs.video_editing.orchestrators.hype.run import _prepare_project_main

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    brief = tmp_path / "brief.txt"
    brief.write_text("make a short thing", encoding="utf-8")

    context, effective_argv = _prepare_project_main(
        ["--project", "demo", "--brief", str(brief), "--brief-slug", "brief-a"]
    )

    assert context is not None
    meta = context.record.get("metadata", {})
    assert isinstance(meta, dict)

    # timeline_slug must be present and match the expected slug
    slug = meta.get(METADATA_KEY_TIMELINE_SLUG)
    assert slug == "brief-a", (
        f"metadata.timeline_slug must be 'brief-a', got {slug!r}"
    )

    # timeline_event_stream_id must be a valid UUID
    esid = meta.get(METADATA_KEY_TIMELINE_EVENT_STREAM_ID)
    assert isinstance(esid, str) and len(esid) > 0, (
        f"metadata.timeline_event_stream_id must be non-empty, got {esid!r}"
    )
    try:
        _uuid.UUID(esid)
    except ValueError:
        pytest.fail(f"metadata.timeline_event_stream_id must be a valid UUID, got {esid!r}")

    # timeline_binding_mode must be 'managed'
    mode = meta.get(METADATA_KEY_TIMELINE_BINDING_MODE)
    assert mode == "managed", (
        f"metadata.timeline_binding_mode must be 'managed', got {mode!r}"
    )


def test_hype_prepare_project_main_returns_none_for_file_only_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove _prepare_project_main returns (None, argv) when --project is absent."""
    from astrid.packs.video_editing.orchestrators.hype.run import _prepare_project_main

    argv = ["--brief", str(tmp_path / "brief.txt"), "--target-duration", "1"]
    context, effective_argv = _prepare_project_main(argv)

    assert context is None, "file-only runs must not bind a managed timeline"
    assert effective_argv == argv, "file-only argv must be returned unchanged"


def test_hype_prepare_project_main_derives_slug_from_brief_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove _prepare_project_main derives slug from brief stem when not generic."""
    from astrid.core.project.run import METADATA_KEY_TIMELINE_SLUG
    from astrid.packs.video_editing.orchestrators.hype.run import _prepare_project_main

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    brief = tmp_path / "my-custom-brief.md"
    brief.write_text("make something cool", encoding="utf-8")

    context, effective_argv = _prepare_project_main(
        ["--project", "demo", "--brief", str(brief)]
    )

    assert context is not None
    meta = context.record.get("metadata", {})
    slug = meta.get(METADATA_KEY_TIMELINE_SLUG)
    assert slug == "my-custom-brief", (
        f"slug should be derived from brief stem, got {slug!r}"
    )


def test_hype_prepare_project_main_falls_back_to_project_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove _prepare_project_main falls back to project slug when brief has generic name."""
    from astrid.core.project.run import METADATA_KEY_TIMELINE_SLUG
    from astrid.packs.video_editing.orchestrators.hype.run import _prepare_project_main

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("my-proj")
    brief = tmp_path / "brief.txt"
    brief.write_text("make it", encoding="utf-8")

    context, effective_argv = _prepare_project_main(
        ["--project", "my-proj", "--brief", str(brief)]
    )

    assert context is not None
    meta = context.record.get("metadata", {})
    slug = meta.get(METADATA_KEY_TIMELINE_SLUG)
    assert slug == "my-proj", (
        f"slug should fall back to project slug for generic brief names, got {slug!r}"
    )


# ── M1 T3: Characterization tests for pre-fix ledger edge cases ─────────


def test_dry_run_with_project_creates_ledger_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dry-run short-circuits before prepare/finalize and writes no ledger."""
    from astrid.core.execution.executor.registry import ExecutorRegistry
    from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)

    registry = ExecutorRegistry([_writer_executor("test.writer")])
    result = run_executor(
        ExecutorRunRequest("test.writer", out="", project="demo", dry_run=True),
        registry,
    )

    assert result.dry_run is True
    records = _project_records(projects_root)
    assert records == []


def test_summarize_run_dir_uses_run_json_status_when_events_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run.json status is the fallback when a project run has no events stream."""
    from astrid.core.task.run_store import _summarize_run_dir

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")

    run_dir = projects_root / "demo" / "runs" / "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    run_dir.mkdir(parents=True, exist_ok=True)

    run_json = {
        "artifacts": {},
        "created_at": "2026-06-01T00:00:00Z",
        "metadata": {},
        "out": str(run_dir),
        "project_slug": "demo",
        "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "schema_version": 1,
        "status": "completed",
        "tool_id": "test.tool",
        "updated_at": "2026-06-01T00:00:00Z",
    }
    (run_dir / "run.json").write_text(
        json.dumps(run_json, indent=2, sort_keys=True), encoding="utf-8"
    )

    status, last_kind, last_ts = _summarize_run_dir(run_dir)

    assert status == "completed"
    assert last_kind == ""
    assert last_ts == ""


def test_summarize_run_dir_keeps_event_stream_status_when_events_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task-run events remain the status authority when events.jsonl exists."""
    from astrid.core.task.run_store import _summarize_run_dir

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")

    run_dir = projects_root / "demo" / "runs" / "01ARZ3NDEKTSV4RRFFQ69G5FAW"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "artifacts": {},
                "created_at": "2026-06-01T00:00:00Z",
                "metadata": {},
                "out": str(run_dir),
                "project_slug": "demo",
                "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
                "schema_version": 1,
                "status": "completed",
                "updated_at": "2026-06-01T00:00:00Z",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "run_started", "ts": "2026-06-01T00:00:01Z"}) + "\n",
        encoding="utf-8",
    )

    status, last_kind, last_ts = _summarize_run_dir(run_dir)

    assert status == "in-flight"
    assert last_kind == "run_started"
    assert last_ts == "2026-06-01T00:00:01Z"


def test_run_show_uses_run_json_status_when_events_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    from astrid.core.task.run_audit import cmd_run_show

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    run_id = "01ARZ3NDEKTSV4RRFFQ69G5FAX"
    run_dir = projects_root / "demo" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "artifacts": {},
                "created_at": "2026-06-01T00:00:00Z",
                "metadata": {},
                "out": str(run_dir),
                "project_slug": "demo",
                "run_id": run_id,
                "schema_version": 1,
                "status": "failed",
                "updated_at": "2026-06-01T00:00:00Z",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    rc = cmd_run_show([run_id, "--project", "demo", "--json"], projects_root=projects_root)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_finalize_without_hype_artifacts_uses_manifest_fallback_from_effective_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manifest fallback uses the effective output directory, not the ledger root."""
    from astrid.core.project.run import (
        finalize_project_run,
        prepare_project_run,
    )

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)

    external_out = tmp_path / "executor-out"
    external_out.mkdir()
    context = prepare_project_run("demo", tool_id="test.stateless", kind="executor", record_out=external_out)

    manifest = {
        "outputs": [
            {"path": "image_001.png", "type": "image/png", "seed": 7},
        ],
        "metadata": {"model": "test-model"},
    }
    manifest_path = external_out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    record = finalize_project_run(
        context,
        status=RunStatus.COMPLETED,
        returncode=0,
    )

    artifacts = record.get("artifacts", {})
    assert record["manifest_path"] == str(manifest_path.resolve())
    assert artifacts["outputs"] == [
        {"path": "image_001.png", "type": "image/png", "seed": 7, "source": "manifest"},
    ]
    assert context.run_root != external_out


def test_finalize_preserves_hype_artifact_precedence_over_manifest_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astrid.core.project.run import finalize_project_run, prepare_project_run

    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)

    context = prepare_project_run("demo", tool_id="test.stateless", kind="executor")
    run_out = resolve_record_path(context.record["out"], context.project_slug, root=projects_root)
    (run_out / "manifest.json").write_text(
        json.dumps({"outputs": [{"path": "image_001.png", "type": "image/png"}]}),
        encoding="utf-8",
    )
    (run_out / "hype.timeline.json").write_text(json.dumps({"clips": []}), encoding="utf-8")
    (run_out / "hype.assets.json").write_text(json.dumps({"assets": {}}), encoding="utf-8")
    (run_out / "hype.metadata.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    record = finalize_project_run(context, status=RunStatus.COMPLETED, returncode=0)

    assert record["manifest_path"] == "runs/{}/manifest.json".format(context.run_id)
    assert sorted(record["artifacts"]) == ["assets", "metadata", "timeline"]
    assert "outputs" not in record["artifacts"]


def test_explicit_project_plus_out_rejected_at_runner_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Characterize: --project --out rejection is strict at runner level.

    This is already tested by test_project_run_rejects_project_plus_out above.
    This characterization test additionally verifies that the rejection happens
    BEFORE any project run directory is created — i.e., it leaves no ledger
    artifacts behind.

    The settled decision SD1 requires this rejection stay strict for explicit
    CLI/direct callers while auto-resolved projects bypass it via metadata.
    """
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    _clear_thread_env(monkeypatch)
    create_project("demo")

    registry = ExecutorRegistry([_writer_executor("test.writer")])

    with pytest.raises(Exception, match="--project cannot be combined with --out"):
        run_executor(
            ExecutorRunRequest("test.writer", out=str(tmp_path / "out"), project="demo"),
            registry,
        )

    # Verify no run directory was created
    runs_glob = list((tmp_path / "projects" / "demo" / "runs").glob("*"))
    assert runs_glob == [], (
        f"Rejection must leave no ledger artifacts; found {len(runs_glob)}"
    )


def test_auto_resolved_project_not_rejected_with_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-resolved project + out= is ledgered without tripping CLI-only rejection."""
    from astrid.core.execution.executor.registry import ExecutorRegistry
    from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

    projects_root, _ = _setup_project_env_conformance(
        tmp_path, monkeypatch, "default"
    )
    out_dir = tmp_path / "auto-out"
    out_dir.mkdir()

    registry = ExecutorRegistry([_writer_executor("test.writer")])
    result = run_executor(
        ExecutorRunRequest("test.writer", out=str(out_dir)), registry
    )

    assert result.returncode == 0
    records = [_read_json(path) for path in sorted((projects_root / "default" / "runs").glob("*/run.json"))]
    assert len(records) == 1
    assert records[0]["project_slug"] == "default"
    assert records[0]["out"] == str(out_dir)
    assert records[0]["metadata"]["project_was_auto_resolved"] is True


def _setup_project_env_conformance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project_slug: str = "demo",
    *,
    with_timeline: bool = True,
) -> tuple[Path, Path]:
    """Set up a temp project and return (projects_root, project_path).

    Same as _setup_project_env in test_run_ledger_conformance.py but defined
    locally to avoid cross-test-module imports.
    """
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    create_project(project_slug)
    if with_timeline:
        create_timeline(project_slug, "main", is_default=True)
    return projects_root, projects_root / project_slug
