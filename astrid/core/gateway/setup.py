"""Local setup planner for Astrid."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from astrid.core.foundation.project_paths import PROJECTS_ROOT_ENV, resolve_projects_root
from astrid.core.foundation.paths import REPO_ROOT


@dataclass(frozen=True)
class SetupStep:
    name: str
    status: str
    detail: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m astrid setup", description="Plan or apply Astrid local setup.")
    parser.add_argument("--apply", action="store_true", help="Apply local setup mutations. Default is dry-run.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable setup output.")
    return parser


def plan_setup(*, apply: bool = False, project_root: str | Path | None = None) -> tuple[SetupStep, ...]:
    root = Path(project_root or REPO_ROOT)
    steps: list[SetupStep] = []
    steps.append(
        SetupStep(
            name="mode",
            status="apply" if apply else "dry-run",
            detail="local mutations enabled" if apply else "no files or dependencies will be changed",
        )
    )
    steps.append(_plan_projects_root(apply=apply))
    return tuple(steps)


def _plan_projects_root(*, apply: bool) -> SetupStep:
    projects_root = resolve_projects_root()
    detail = f"{projects_root} ({PROJECTS_ROOT_ENV} override supported)"
    if projects_root.is_dir():
        return SetupStep(name="projects root", status="ok", detail=detail)
    if apply:
        projects_root.mkdir(parents=True, exist_ok=True)
        return SetupStep(name="projects root", status="applied", detail=f"created {detail}")
    return SetupStep(name="projects root", status="planned", detail=f"will create {detail}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    steps = plan_setup(apply=bool(args.apply))
    if args.json:
        payload = {
            "applied": bool(args.apply),
            "steps": [asdict(step) for step in steps],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("Astrid setup")
    if not args.apply:
        print("dry-run: pass --apply to apply local setup mutations")
    for step in steps:
        print(f"[{step.status}] {step.name}: {step.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
