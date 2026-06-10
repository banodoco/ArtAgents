"""Regression tests promoted from Sprint 0 spike findings."""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

from astrid.core.contracts.schema import CommandSpec
from astrid.core.execution.orchestrator.runner import (
    OrchestratorRunRequest,
    _run_command_orchestrator,
)
from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec
from astrid.core.task.events import (
    ZERO_HASH,
    StaleTailError,
    append_event_locked,
    verify_chain,
)


def test_command_runtime_orchestrator_preserves_astrid_session_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "child-env.json"
    session_id = "S-spike-command-runtime"
    monkeypatch.setenv("ASTRID_SESSION_ID", session_id)

    code = (
        "import json, os, sys; "
        "json.dump({"
        "'session_id': os.environ.get('ASTRID_SESSION_ID'), "
        "'sentinel': os.environ.get('ORCH_SENTINEL'), "
        "'internal': os.environ.get('ASTRID_INTERNAL_INVOCATION')"
        "}, open(sys.argv[1], 'w', encoding='utf-8'), sort_keys=True)"
    )
    orchestrator = OrchestratorDefinition(
        id="test.command_env",
        name="Command Env",
        kind="built_in",
        version="0.0.0",
        runtime=RuntimeSpec(
            kind="command",
            command=CommandSpec(
                argv=(sys.executable, "-c", code, str(output_path)),
                cwd=str(tmp_path),
                env={"ORCH_SENTINEL": "from-runtime-env"},
            ),
        ),
    )

    result = _run_command_orchestrator(
        orchestrator,
        OrchestratorRunRequest(orchestrator_id=orchestrator.id),
        {},
    )

    assert result.returncode == 0
    observed = json.loads(output_path.read_text(encoding="utf-8"))
    assert observed == {
        "internal": "1",
        "sentinel": "from-runtime-env",
        "session_id": session_id,
    }


def _seed_events_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "lease.json").write_text(
        json.dumps(
            {
                "writer_epoch": 0,
                "attached_session_id": "shared-writer",
                "plan_hash": "",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").touch()


def _append_once_with_initial_tail(
    barrier: mp.Barrier,
    run_dir_str: str,
    worker_id: str,
    result_queue: mp.Queue,
) -> None:
    run_dir = Path(run_dir_str)
    barrier.wait()
    try:
        stored = append_event_locked(
            run_dir,
            {"kind": "race_once", "worker": worker_id},
            expected_writer_epoch=0,
            expected_prev_hash=ZERO_HASH,
        )
        result_queue.put({"status": "ok", "worker": worker_id, "hash": stored["hash"]})
    except StaleTailError as exc:
        result_queue.put(
            {
                "status": "stale_tail",
                "worker": worker_id,
                "expected": exc.expected,
                "actual": exc.actual,
            }
        )


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="append_event_locked uses POSIX fcntl locks",
)
def test_append_event_locked_serializes_events_jsonl_with_tail_cas(tmp_path: Path) -> None:
    run_dir = tmp_path / "project" / "runs" / "run-1"
    _seed_events_run(run_dir)

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    queue: mp.Queue = ctx.Queue()
    p1 = ctx.Process(
        target=_append_once_with_initial_tail,
        args=(barrier, str(run_dir), "A", queue),
    )
    p2 = ctx.Process(
        target=_append_once_with_initial_tail,
        args=(barrier, str(run_dir), "B", queue),
    )

    p1.start()
    p2.start()
    p1.join(timeout=20)
    p2.join(timeout=20)

    assert not p1.is_alive() and not p2.is_alive()
    assert p1.exitcode == 0 and p2.exitcode == 0

    results: list[dict[str, str]] = []
    while not queue.empty():
        results.append(queue.get_nowait())
    statuses = sorted(result["status"] for result in results)
    assert statuses == ["ok", "stale_tail"], results

    events_path = run_dir / "events.jsonl"
    raw_lines = events_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 1
    stored = json.loads(raw_lines[0])
    assert stored["kind"] == "race_once"
    assert stored["worker"] in {"A", "B"}

    ok, last_index, err = verify_chain(events_path)
    assert ok is True, err
    assert last_index == 0
