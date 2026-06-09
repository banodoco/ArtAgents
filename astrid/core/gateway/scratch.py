"""Handler for ``astrid scratch run`` — throwaway Python scripts with project context."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from astrid.core.contracts.run_status import RunStatus
from astrid.core.project.run import (
    finalize_project_run,
    prepare_project_run,
)
from astrid.core.runtime.log_capture import (
    open_run_log_capture,
    run_subprocess_with_capture,
)
from astrid.core.subprocess_env import build_child_subprocess_env

from . import ASTRID_GATEWAY_RESOLVED_PROJECT_ENV, DEFAULT_PROJECT_SLUG


def dispatch_scratch(args: list[str]) -> int:
    """Run a throwaway Python script with default project context."""
    parser = argparse.ArgumentParser(prog="astrid scratch")
    sub = parser.add_subparsers(dest="scratch_command")
    run_parser = sub.add_parser("run", help="Run a throwaway Python script")
    run_parser.add_argument("file", help="Python file to run")
    run_parser.add_argument(
        "extra", nargs=argparse.REMAINDER, help="Extra arguments forwarded to the script"
    )

    parsed = parser.parse_args(args)
    if parsed.scratch_command != "run":
        parser.print_help()
        return 1

    file_path = Path(parsed.file)
    if not file_path.is_file():
        print(f"scratch: file not found: {file_path}", file=sys.__stderr__)
        return 1

    project_slug = os.environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    if not project_slug:
        try:
            from astrid.core.project.paths import resolve_projects_root
            from astrid.core.session.binding import resolve_current_session_with_fs_fallback

            session = resolve_current_session_with_fs_fallback(
                projects_root=resolve_projects_root(),
            )
            if session and getattr(session, "project", None):
                project_slug = session.project
        except Exception:
            pass
    if not project_slug:
        project_slug = DEFAULT_PROJECT_SLUG

    extra = parsed.extra or []
    argv = [str(file_path)] + extra

    context = prepare_project_run(
        project_slug,
        tool_id="scratch.run",
        kind="scratch",
        argv=argv,
        requires_timeline=False,
        auto_bound=True,
        invocation="scratch",
    )

    child_env = build_child_subprocess_env(
        explicit_env={
            "ASTRID_PROJECT_RUN": "1",
        },
    )
    with open_run_log_capture(context.run_root) as logs:
        returncode = run_subprocess_with_capture(
            [sys.executable, str(file_path)] + extra,
            env=child_env,
            stdout_log=logs.stdout,
            stderr_log=logs.stderr,
        )

    status = RunStatus.COMPLETED if returncode == 0 else RunStatus.FAILED
    finalize_project_run(
        context,
        status=status,
        returncode=returncode,
    )

    return returncode
