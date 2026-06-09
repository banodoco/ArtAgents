"""Author-test fixture replay driver.

``run_fixture`` drives a compiled orchestrator plan through the gate inside a
scratch projects root with ASTRID_AUTHOR_TEST=1, auto-approving attested
steps. The resulting events.jsonl path is returned for the diff/regenerate
caller in ``orchestrate.cli``.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import Optional

from astrid.core.session.current_run_state import read_current_run_state
from astrid.core.foundation.project_paths import PROJECTS_ROOT_ENV
from astrid.core.project.project import create_project
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.model import Session
from astrid.core.session.paths import ASTRID_HOME_ENV, session_path
from astrid.core.env_vars import ASTRID_AUTHOR_TEST
from astrid.core.task.env import (
    ASTRID_ACTOR,
    TASK_ITEM_ID_ENV,
    TASK_ITERATION_ENV,
    TASK_PROJECT_ENV,
    TASK_RUN_ID_ENV,
    TASK_STEP_ID_ENV,
    child_subprocess_env,
)
from astrid.core.task.events import read_events
from astrid.core.task.gate import (
    TaskRunGateError,
    gate_command,
    peek_current_step,
    record_dispatch_complete,
)
from astrid.core.task.lifecycle import cmd_start
from astrid.core.task.lifecycle_ack import cmd_ack
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    is_attested_kind,
    is_code_kind,
    load_plan,
    step_dir_for_path,
)
from astrid.core.timeline.crud import create_timeline
from astrid.core.orchestrate.compile import compile_to_path

_MAX_ITERATIONS = 200

# Env vars that gate dispatch (apply_task_run_env) injects into os.environ.
# We snapshot these before run_fixture mutates anything and restore in finally
# so a fixture replay never leaks task-run state into the surrounding test
# process or shell.
_MANAGED_ENV_VARS = (
    ASTRID_HOME_ENV,
    ASTRID_SESSION_ID_ENV,
    PROJECTS_ROOT_ENV,
    ASTRID_AUTHOR_TEST,
    ASTRID_ACTOR,
    TASK_RUN_ID_ENV,
    TASK_PROJECT_ENV,
    TASK_STEP_ID_ENV,
    TASK_ITEM_ID_ENV,
    TASK_ITERATION_ENV,
)


def _bind_author_test_session(project_slug: str, projects_root: Path) -> None:
    sid = f"S-author-test-{project_slug}"
    os.environ[ASTRID_HOME_ENV] = str(projects_root / ".astrid-author-test")
    os.environ[PROJECTS_ROOT_ENV] = str(projects_root)
    os.environ[ASTRID_SESSION_ID_ENV] = sid
    sess = Session(
        id=sid,
        project=project_slug,
        agent_id="author_test",
        attached_at="2026-05-11T00:00:00Z",
        last_used_at="2026-05-11T00:00:00Z",
        role="writer",
        timeline=None,
        run_id=None,
    )
    path = session_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    sess.to_json(path)


def _seed_author_test_produces(*, slug: str, run_id: str, step, path_tuple, projects_root: Path) -> None:
    """Create minimal declared outputs for auto-approved author-test steps."""
    for produced in getattr(step, "produces", ()) or ():
        target = (
            step_dir_for_path(
                slug,
                run_id,
                path_tuple,
                step_version=step.version,
                root=projects_root,
            )
            / "produces"
            / produced.path
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".json":
            target.write_text('{"verdict":"ship"}\n', encoding="utf-8")
        else:
            target.write_text("ship\n", encoding="utf-8")


def _snapshot_env(names: tuple[str, ...]) -> dict[str, Optional[str]]:
    return {name: os.environ.get(name) for name in names}


def _restore_env(snapshot: dict[str, Optional[str]]) -> None:
    for name, value in snapshot.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _wait_for_adapter_completion(decision) -> int:
    """Return the exit status for an already-dispatched adapter step."""
    adapter_kind = getattr(decision, "adapter", None)
    if adapter_kind == "manual":
        return 0

    pid = getattr(decision, "pid", None)
    if pid is None:
        return -1

    try:
        _, status = os.waitpid(pid, 0)
    except (ChildProcessError, ProcessLookupError):
        return -1

    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return -abs(os.WTERMSIG(status))
    return -1


def _run_fallback_subprocess(cmd_argv: list[str]) -> CompletedProcess[str]:
    """Legacy fallback for code steps that were not adapter-dispatched."""
    return subprocess.run(
        cmd_argv,
        env=child_subprocess_env(),
        check=False,
        text=True,
    )


def _finish_code_step(decision, cmd_argv: list[str]) -> None:
    if getattr(decision, "adapter", None) is None:
        returncode = _run_fallback_subprocess(cmd_argv).returncode
    else:
        returncode = _wait_for_adapter_completion(decision)
    record_dispatch_complete(decision, returncode)


def run_fixture(
    *,
    qualified_id: str,
    fixture_dir: Optional[Path],
    packs_root: Path,
    projects_root: Path,
    project_slug: str = "author_test",
    run_id: str = "fixture_run",
) -> Path:
    """Replay the orchestrator plan against the fixture inside ``projects_root``.

    Returns the path to ``events.jsonl`` for the resulting run. Raises
    ``RuntimeError`` if the loop fails to make progress within the cap, or if
    the gate / lifecycle helpers reject a step (the original error is wrapped).
    """
    snapshot = _snapshot_env(_MANAGED_ENV_VARS)
    os.environ[ASTRID_AUTHOR_TEST] = "1"
    os.environ[ASTRID_ACTOR] = "author_test"
    try:
        project_root = projects_root / project_slug
        if fixture_dir is not None and Path(fixture_dir).exists():
            shutil.copytree(fixture_dir, project_root, dirs_exist_ok=True)
        project_root.mkdir(parents=True, exist_ok=True)
        # cmd_start now requires the project to be registered (via project.json)
        # before it will accept --project. Idempotent so a fixture-supplied
        # project.json is preserved.
        create_project(project_slug, root=projects_root, exist_ok=True)
        create_timeline(project_slug, "main", root=projects_root, is_default=True)
        _bind_author_test_session(project_slug, projects_root)
        pack, _, name = qualified_id.partition(".")
        if pack and name:
            build_path = packs_root / pack / "build" / f"{name}.json"
            if not build_path.is_file():
                compile_to_path(qualified_id, packs_root=packs_root)

        rc = cmd_start(
            [qualified_id, "--project", project_slug, "--name", run_id],
            packs_root=packs_root,
            projects_root=projects_root,
        )
        if rc != 0:
            raise RuntimeError(
                f"author test: cmd_start failed with rc={rc} for {qualified_id}"
            )

        plan_path = project_root / "plan.json"
        events_path = project_root / "runs" / run_id / "events.jsonl"

        for _ in range(_MAX_ITERATIONS):
            active = read_current_run_state(project_slug, root=projects_root)
            if active is None:
                break
            plan = load_plan(plan_path)
            events = read_events(events_path)
            peek = peek_current_step(
                plan,
                events,
                project_slug,
                project_root=project_root,
                run_id=run_id,
            )
            if peek.exhausted or peek.step is None:
                break

            step = peek.step
            path_str = STEP_PATH_SEP.join(peek.path_tuple)

            if is_code_kind(step):
                cmd_str = step.command
                cmd_argv = shlex.split(cmd_str)
                try:
                    decision = gate_command(
                        project_slug,
                        cmd_str,
                        cmd_argv,
                        root=projects_root,
                    )
                except TaskRunGateError as exc:
                    raise RuntimeError(
                        f"author test: gate rejected code step {path_str!r}: {exc.reason}"
                    ) from exc
                _finish_code_step(decision, cmd_argv)
                continue

            if is_attested_kind(step):
                _seed_author_test_produces(
                    slug=project_slug,
                    run_id=run_id,
                    step=step,
                    path_tuple=peek.path_tuple,
                    projects_root=projects_root,
                )
                if step.ack is not None and step.ack.kind == "agent":
                    flag_pair = ["--agent", "author_test"]
                else:
                    flag_pair = ["--human", "author_test"]
                rc = cmd_ack(
                    [
                        path_str,
                        "--project",
                        project_slug,
                        "--decision",
                        "approve",
                        *flag_pair,
                    ],
                    projects_root=projects_root,
                )
                if rc != 0:
                    raise RuntimeError(
                        f"author test: cmd_ack failed for attested step {path_str!r} "
                        f"(rc={rc})"
                    )
                continue

            raise RuntimeError(
                f"author test: unsupported peek step kind {type(step).__name__} "
                f"at {path_str!r}"
            )
        else:
            raise RuntimeError(
                f"author test: exceeded {_MAX_ITERATIONS} iterations without "
                f"reaching plan completion (likely an author bug; check plan)"
            )

        return events_path
    finally:
        _restore_env(snapshot)
