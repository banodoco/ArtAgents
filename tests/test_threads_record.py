from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from astrid.contracts.schema import CommandSpec, Output, Port
from astrid.core.executor.registry import ExecutorRegistry
from astrid.core.executor.runner import ExecutorRunRequest, ExecutorRunnerError, run_executor
from astrid.core.executor.schema import ExecutorDefinition
from astrid.core.orchestrator.registry import OrchestratorRegistry
from astrid.core.orchestrator.runner import OrchestratorRunRequest, run_orchestrator
from astrid.core.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.threads.record import build_run_record, finalize_run_record


THREAD_ID = "01ARZ3NDEKTSV4RRFFQ69G5FW0"
RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FW1"


def test_executor_runtime_does_not_bind_thread_or_inject_thread_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    out = repo / "runs" / "success"
    registry = ExecutorRegistry([_writer_executor("test.writer")])

    result = run_executor(ExecutorRunRequest("test.writer", out=out), registry)

    assert result.returncode == 0
    assert (out / "result.txt").read_text(encoding="utf-8") == ":"
    assert not (out / "run.json").exists()
    assert not (repo / ".astrid" / "threads.json").exists()


def test_executor_runtime_errors_do_not_finalize_thread_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    failed_out = repo / "runs" / "failed"
    registry = ExecutorRegistry([_exit_executor("test.exits", 7), _requires_input_executor("test.requires")])

    result = run_executor(ExecutorRunRequest("test.exits", out=failed_out), registry)

    assert result.returncode == 7
    assert not (failed_out / "run.json").exists()

    error_out = repo / "runs" / "error"
    with pytest.raises(ExecutorRunnerError):
        run_executor(ExecutorRunRequest("test.requires", out=error_out), registry)
    assert not (error_out / "run.json").exists()
    assert not (repo / ".astrid" / "threads.json").exists()


def test_thread_compatibility_env_is_ignored_by_generic_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    registry = ExecutorRegistry([_writer_executor("test.writer"), _exit_executor("test.noout", 0)])

    monkeypatch.setenv("ASTRID_THREADS_OFF", "1")
    run_executor(ExecutorRunRequest("test.writer", out=repo / "runs" / "off"), registry)
    monkeypatch.delenv("ASTRID_THREADS_OFF")
    monkeypatch.setenv("ASTRID_THREAD_INHERITED", "1")
    run_executor(ExecutorRunRequest("test.writer", out=repo / "runs" / "inherited"), registry)
    monkeypatch.delenv("ASTRID_THREAD_INHERITED")

    assert not (repo / "runs" / "off" / "run.json").exists()
    assert not (repo / "runs" / "inherited" / "run.json").exists()
    assert (repo / "runs" / "off" / "result.txt").read_text(encoding="utf-8") == ":"
    assert (repo / "runs" / "inherited" / "result.txt").read_text(encoding="utf-8") == ":"


def test_upload_youtube_is_zero_artifact_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    with mock.patch(
        "astrid.packs.youtube.executors.upload.src.social_publish.publish_youtube_video",
        return_value={"url": "https://youtube.example/video"},
    ):
        result = run_executor(
            ExecutorRunRequest(
                "youtube.upload",
                out="",
                inputs={
                    "video_url": "https://example.invalid/video.mp4",
                    "title": "Title",
                    "description": "Description",
                },
            )
        )
    assert result.payload["url"] == "https://youtube.example/video"
    assert not (repo / ".astrid").exists()


def test_internal_thread_record_redaction_private_brief_and_external_service_trim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    out = repo / "runs" / "private-case"
    private = out / "private"
    private.mkdir(parents=True)
    brief = private / "brief.txt"
    brief.write_text("secret brief", encoding="utf-8")
    record = build_run_record(
        run_id=RUN_ID,
        thread_id=THREAD_ID,
        kind="executor",
        executor_id="test.writer",
        out_path=out,
        repo_root=repo,
        brief=brief,
        cli_args=["--input=OPENAI_API_KEY=sk-test"],
        inputs={
            "OPENAI_API_KEY": "sk-test",
            "external_service_calls": [
                {
                    "model": "gpt-image-2",
                    "model_version": "2026-01-01",
                    "request_id": "req_123",
                    "latency_ms": 99,
                }
            ],
        },
    )

    assert "sk-test" not in json.dumps(record)
    assert any(arg == "--input=OPENAI_API_KEY=***REDACTED***" for arg in record["cli_args_redacted"])
    assert record["brief_content_sha256"]
    assert not (out / "brief.copy.txt").exists()
    brief_artifact = next(item for item in record["input_artifacts"] if item["kind"] == "brief")
    assert brief_artifact["private"] is True
    assert "path" not in brief_artifact
    assert brief_artifact["sha256"]
    assert record["external_service_calls"] == [
        {"model": "gpt-image-2", "model_version": "2026-01-01", "request_id": "req_123"}
    ]


def test_orchestrator_command_runtime_does_not_bind_thread_or_propagate_thread_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    out = repo / "runs" / "orch"
    registry = OrchestratorRegistry([_writer_orchestrator("test.orch")])

    result = run_orchestrator(OrchestratorRunRequest("test.orch", out=out), registry)

    assert result.returncode == 0
    env_text = (out / "orch-env.txt").read_text(encoding="utf-8")
    assert env_text == ":"
    assert not (out / "run.json").exists()
    assert not (repo / ".astrid" / "threads.json").exists()


def test_internal_thread_record_preserves_parent_lineage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    out = repo / "runs" / "chosen"
    parent_run_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"

    record = build_run_record(
        run_id=RUN_ID,
        thread_id=THREAD_ID,
        kind="executor",
        executor_id="test.writer",
        out_path=out,
        repo_root=repo,
        parent_run_ids=[{"kind": "chosen", "run_id": parent_run_id}],
    )
    assert record["parent_run_ids"] == [{"kind": "chosen", "run_id": parent_run_id}]


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("ASTRID_REPO_ROOT", str(repo))
    for name in ("ASTRID_THREADS_OFF", "ASTRID_THREAD_INHERITED", "ASTRID_THREAD_ID", "ASTRID_RUN_ID", "ASTRID_PARENT_RUN_ID"):
        monkeypatch.delenv(name, raising=False)
    return repo


def _writer_executor(executor_id: str) -> ExecutorDefinition:
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "out = Path(sys.argv[1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'result.txt').write_text(os.environ.get('ASTRID_THREAD_INHERITED', '') + ':' + os.environ.get('ASTRID_THREAD_ID', ''), encoding='utf-8')\n"
    )
    return ExecutorDefinition(
        id=executor_id,
        name="Writer",
        kind="external",
        version="1.0",
        command=CommandSpec(argv=(sys.executable, "-c", script, "{out}")),
        outputs=(Output(name="result", type="file", path_template="{out}/result.txt"),),
    )


def _exit_executor(executor_id: str, code: int) -> ExecutorDefinition:
    return ExecutorDefinition(
        id=executor_id,
        name="Exit",
        kind="external",
        version="1.0",
        command=CommandSpec(argv=(sys.executable, "-c", f"import sys; sys.exit({code})")),
    )


def _requires_input_executor(executor_id: str) -> ExecutorDefinition:
    return ExecutorDefinition(
        id=executor_id,
        name="Requires Input",
        kind="external",
        version="1.0",
        inputs=(Port(name="needed", type="string", required=True),),
        command=CommandSpec(argv=(sys.executable, "-c", "print('unused')")),
    )


def _writer_orchestrator(orchestrator_id: str) -> OrchestratorDefinition:
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "out = Path(sys.argv[1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'orch-env.txt').write_text(os.environ.get('ASTRID_THREAD_INHERITED', '') + ':' + os.environ.get('ASTRID_THREAD_ID', ''), encoding='utf-8')\n"
    )
    return OrchestratorDefinition(
        id=orchestrator_id,
        name="Orchestrator",
        kind="built_in",
        version="1.0",
        runtime=RuntimeSpec(kind="command", command=CommandSpec(argv=(sys.executable, "-c", script, "{out}"))),
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
