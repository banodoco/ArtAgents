"""CLI wrapper for the Sprint 0 two-tab concurrency harness."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from astrid.core.session.binding import ASTRID_SESSION_ID_ENV, SESSION_FILE_NAME
from astrid.core.session.model import Session, now_iso
from astrid.core.session.paths import SESSIONS_DIRNAME
from tests.concurrency.two_tab_harness import race_two_tabs

_DEFAULT_PROJECT_SLUG = "reshape-two-tab"
_DEFAULT_RUN_ID = "run-1"
_DEFAULT_SESSION_ID = "S-reshape-two-tab"
_DEFAULT_AGENT_ID = "agent:reshape-two-tab"
_DEFAULT_STEP_ID = "two-tab"


def _parse_env_overlay(values: Sequence[str]) -> dict[str, str | None]:
    overlay: dict[str, str | None] = {}
    for item in values:
        if "=" not in item:
            overlay[item] = None
            continue
        key, _, value = item.partition("=")
        if not key:
            raise SystemExit("ERROR: --env entries must use KEY=VALUE or KEY")
        overlay[key] = value
    return overlay


def _format_command(command: str, env: dict[str, str]) -> list[str]:
    replacements = {
        "projects_root": env["ASTRID_PROJECTS_ROOT"],
        "project_slug": env["ASTRID_TASK_PROJECT"],
        "run_id": env["ASTRID_TASK_RUN_ID"],
        "session_id": env[ASTRID_SESSION_ID_ENV],
        "astrid_home": env["ASTRID_HOME"],
    }
    formatted = command
    for key, value in replacements.items():
        formatted = formatted.replace("{" + key + "}", shlex.quote(value))
    return shlex.split(formatted)


def _prepare_roots(
    *,
    projects_root: Path | None,
    astrid_home: Path | None,
    project_slug: str,
    run_id: str,
    session_id: str,
    agent_id: str,
) -> tuple[Path, Path, dict[str, str]]:
    if projects_root is None:
        projects_root = Path(tempfile.mkdtemp(prefix="astrid-two-tab-projects-"))
    else:
        projects_root = projects_root.expanduser().resolve()
        projects_root.mkdir(parents=True, exist_ok=True)
    if astrid_home is None:
        astrid_home = Path(tempfile.mkdtemp(prefix="astrid-two-tab-home-"))
    else:
        astrid_home = astrid_home.expanduser().resolve()
        astrid_home.mkdir(parents=True, exist_ok=True)

    project_dir = projects_root / project_slug
    run_dir = project_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    pointer = project_dir / SESSION_FILE_NAME
    pointer.write_text(f"{ASTRID_SESSION_ID_ENV}={session_id}\n", encoding="utf-8")
    try:
        os.chmod(pointer, 0o600)
    except OSError:
        pass

    sessions_dir = astrid_home / SESSIONS_DIRNAME
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session = Session(
        id=session_id,
        project=project_slug,
        run_id=run_id,
        agent_id=agent_id,
        attached_at=now_iso(),
        last_used_at=now_iso(),
        role="writer",
    )
    session.to_json(sessions_dir / f"{session_id}.json")

    env = {
        "ASTRID_HOME": str(astrid_home),
        "ASTRID_PROJECTS_ROOT": str(projects_root),
        ASTRID_SESSION_ID_ENV: session_id,
        "ASTRID_TASK_PROJECT": project_slug,
        "ASTRID_TASK_RUN_ID": run_id,
        "ASTRID_TASK_STEP_ID": _DEFAULT_STEP_ID,
        "ASTRID_PROJECT_RUN": run_id,
    }
    return projects_root, astrid_home, env


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run two commands with isolated Sprint 0 two-tab env.")
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument("--command", help="Command template to run in both tabs.")
    command_group.add_argument("--command-a", help="Command template to run in tab A.")
    parser.add_argument("--command-b", help="Command template to run in tab B; defaults to --command-a.")
    parser.add_argument("--projects-root", type=Path, help="Projects root to use. Defaults to a new temp root.")
    parser.add_argument("--astrid-home", type=Path, help="ASTRID_HOME to use. Defaults to a new temp home.")
    parser.add_argument("--project-slug", default=_DEFAULT_PROJECT_SLUG)
    parser.add_argument("--run-id", default=_DEFAULT_RUN_ID)
    parser.add_argument("--session-id", default=_DEFAULT_SESSION_ID)
    parser.add_argument("--agent-id", default=_DEFAULT_AGENT_ID)
    parser.add_argument("--env", action="append", default=[], help="Extra env overlay KEY=VALUE; KEY unsets.")
    parser.add_argument("--expected-winner-count", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument(
        "--race-profile",
        choices=("ci", "heavy"),
        default=os.environ.get("ASTRID_TWO_TAB_RACE_PROFILE", "ci"),
        help="ci keeps short timeouts; heavy requires explicit opt-in.",
    )
    parser.add_argument(
        "--allow-heavy",
        action="store_true",
        help="Allow the heavy race profile outside explicit local opt-in.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.race_profile == "heavy" and not (args.allow_heavy or os.environ.get("ASTRID_TWO_TAB_ALLOW_HEAVY") == "1"):
        raise SystemExit("ERROR: heavy two-tab races require --allow-heavy or ASTRID_TWO_TAB_ALLOW_HEAVY=1")

    projects_root, astrid_home, env = _prepare_roots(
        projects_root=args.projects_root,
        astrid_home=args.astrid_home,
        project_slug=args.project_slug,
        run_id=args.run_id,
        session_id=args.session_id,
        agent_id=args.agent_id,
    )
    env.update({key: value for key, value in _parse_env_overlay(args.env).items() if value is not None})
    for key, value in _parse_env_overlay(args.env).items():
        if value is None:
            env.pop(key, None)

    command_a_template = args.command or args.command_a
    command_b_template = args.command or args.command_b or args.command_a
    command_a = _format_command(command_a_template, env)
    command_b = _format_command(command_b_template, env)
    timeout = args.timeout_seconds
    if timeout is None:
        timeout = 60.0 if args.race_profile == "heavy" else 20.0

    def setup() -> Path:
        return projects_root / args.project_slug / "runs" / args.run_id

    result = race_two_tabs(
        setup_fn=setup,
        p1_command=command_a,
        p2_command=command_b,
        env_overlay=env,
        expected_winner_count=args.expected_winner_count,
        timeout_seconds=timeout,
    )
    payload = {
        "projects_root": str(projects_root),
        "astrid_home": str(astrid_home),
        "project_slug": args.project_slug,
        "run_id": args.run_id,
        "session_id": args.session_id,
        "race_profile": args.race_profile,
        "result": asdict(result),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
