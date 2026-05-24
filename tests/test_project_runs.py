from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from astrid.contracts.schema import CommandSpec, Port
from astrid.core.executor.registry import ExecutorRegistry
from astrid.core.executor.runner import ExecutorRunRequest, ExecutorRunnerError, run_executor
from astrid.core.executor.schema import ConditionSpec, ExecutorDefinition
from astrid.core.orchestrator.registry import OrchestratorRegistry
from astrid.core.orchestrator.runner import OrchestratorRunRequest, run_orchestrator
from astrid.core.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.core.project import paths
from astrid.core.project.project import create_project
from astrid.core.timeline.crud import create_timeline
from astrid.packs.builtin.hype import run as hype


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
    with pytest.raises(ExecutorRunnerError):
        run_executor(ExecutorRunRequest("test.requires", out="", project="demo"), registry)
    skipped = run_executor(ExecutorRunRequest("test.skip", out="", project="demo", inputs={"skip_me": "1"}), registry)

    assert success.returncode == 0
    assert skipped.skipped is True
    records = _project_records(projects_root)
    assert [record["status"] for record in records] == ["success", "error", "skipped"]
    writer_out = Path(records[0]["out"])
    assert (writer_out / "env.txt").read_text(encoding="utf-8") == "1"
    assert (writer_out / "run.json").exists()
    assert not (repo / ".astrid" / "threads.json").exists()


def test_executor_legacy_out_no_longer_writes_thread_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    _clear_thread_env(monkeypatch)
    registry = ExecutorRegistry([_writer_executor("test.writer")])
    out = repo / "runs" / "legacy"

    result = run_executor(ExecutorRunRequest("test.writer", out=out), registry)

    assert result.returncode == 0
    assert not (out / "run.json").exists()
    assert not (repo / ".astrid" / "threads.json").exists()
    assert not (tmp_path / "projects").exists()


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
    assert record["status"] == "success"
    assert record["tool_id"] == "test.orch"
    assert (Path(record["out"]) / "orch-env.txt").read_text(encoding="utf-8") == "1"

    hype_registry = OrchestratorRegistry([_hype_command_orchestrator()])
    dry = run_orchestrator(
        OrchestratorRunRequest(
            "builtin.hype",
            project="demo",
            dry_run=True,
            orchestrator_args=("--brief", str(tmp_path / "brief.txt"), "--target-duration", "1"),
        ),
        hype_registry,
    )
    assert dry.dry_run is True
    assert "--out" in dry.command
    assert str(projects_root / "demo" / "runs") in " ".join(dry.command)


def test_direct_hype_project_validation_error_and_nested_artifact_mirroring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(projects_root))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    create_timeline("demo", "main", is_default=True)

    code = hype.main(["--project", "demo", "--target-duration", "1"])
    assert code == 2
    error_record = _project_records(projects_root)[0]
    assert error_record["status"] == "error"
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
    assert success_record["status"] == "success"
    assert sorted(success_record["artifacts"]) == ["assets", "metadata", "timeline"]
    assert success_record["artifacts"]["timeline"]["source_path"].endswith("briefs/brief-a/hype.timeline.json")
    assert (Path(success_record["out"]) / "timeline.json").exists()


def test_project_run_rejects_project_plus_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    _clear_thread_env(monkeypatch)
    create_project("demo")
    registry = ExecutorRegistry([_writer_executor("test.writer")])

    with pytest.raises(Exception, match="--project cannot be combined with --out"):
        run_executor(ExecutorRunRequest("test.writer", out=tmp_path / "out", project="demo"), registry)
    assert list((tmp_path / "projects" / "demo" / "runs").glob("*")) == []


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
        tool_id="astrid.core.worker.banodoco_worker",
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
        id="builtin.hype",
        name="Hype",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(
            kind="command",
            command=CommandSpec(argv=(sys.executable, "-m", "astrid.packs.builtin.hype.run", "{orchestrator_args}")),
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
    from astrid.packs.builtin.hype.run import _prepare_project_main
    from astrid.threads.ids import is_ulid

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
    from astrid.packs.builtin.hype.run import _prepare_project_main
    from astrid.core.project.run import (
        METADATA_KEY_TIMELINE_SLUG,
        METADATA_KEY_TIMELINE_EVENT_STREAM_ID,
        METADATA_KEY_TIMELINE_BINDING_MODE,
    )
    import uuid as _uuid

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
    from astrid.packs.builtin.hype.run import _prepare_project_main

    argv = ["--brief", str(tmp_path / "brief.txt"), "--target-duration", "1"]
    context, effective_argv = _prepare_project_main(argv)

    assert context is None, "file-only runs must not bind a managed timeline"
    assert effective_argv == argv, "file-only argv must be returned unchanged"


def test_hype_prepare_project_main_derives_slug_from_brief_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove _prepare_project_main derives slug from brief stem when not generic."""
    from astrid.packs.builtin.hype.run import _prepare_project_main
    from astrid.core.project.run import METADATA_KEY_TIMELINE_SLUG

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
    from astrid.packs.builtin.hype.run import _prepare_project_main
    from astrid.core.project.run import METADATA_KEY_TIMELINE_SLUG

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
