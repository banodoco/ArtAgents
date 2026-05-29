"""Local setup planner for Astrid."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from astrid._paths import REPO_ROOT
from astrid.core.element.install import install_element
from astrid.core.element.registry import load_default_registry as load_element_registry
from astrid.core.project.paths import PROJECTS_ROOT_ENV, resolve_projects_root


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
    steps.extend(_plan_root_skill_symlinks(root, apply=apply))

    registry = load_element_registry(project_root=root)
    for element in registry.list():
        result = install_element(element, project_root=root, dry_run=not apply)
        plan = result.plan
        if plan.noop_reason:
            steps.append(SetupStep(name="elements install", status="skipped", detail=f"{element.kind}/{element.id}: {plan.noop_reason}"))
            continue
        status = "applied" if apply else "planned"
        details = "; ".join(plan.command_lines())
        steps.append(SetupStep(name="elements install", status=status, detail=f"{element.kind}/{element.id}: {details}"))
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


def _plan_root_skill_symlinks(root: Path, *, apply: bool) -> tuple[SetupStep, ...]:
    """Ensure root agent-doc aliases point directly at the core skill source."""
    target = Path("astrid") / "packs" / "_core" / "skill" / "SKILL.md"
    skill = root / target
    if not skill.is_file():
        return (
            SetupStep(
                name="root skill symlinks",
                status="warn",
                detail=f"{skill} missing; cannot link AGENTS.md or SKILL.md",
            ),
        )
    target_text = target.as_posix()
    return tuple(
        _plan_root_skill_symlink(root / name, root=root, target=target_text, skill=skill, apply=apply)
        for name in ("AGENTS.md", "SKILL.md")
    )


def _plan_root_skill_symlink(path: Path, *, root: Path, target: str, skill: Path, apply: bool) -> SetupStep:
    name = f"{path.name.lower()} symlink"
    if path.is_symlink() and (root / path.readlink()).resolve() == skill.resolve():
        if path.readlink().as_posix() == target:
            return SetupStep(name=name, status="ok", detail=f"{path.name} -> {target}")
        status = "applied" if apply else "planned"
        detail = f"{'updated' if apply else 'will update'} {path.name} -> {target}"
        if apply:
            path.unlink()
            path.symlink_to(target)
        return SetupStep(name=name, status=status, detail=detail)
    if path.is_symlink() and not (root / path.readlink()).exists():
        kind = "broken symlink"
    elif path.is_symlink():
        kind = "wrong symlink"
    else:
        kind = "regular file"
    if not path.exists() and not path.is_symlink():
        if apply:
            path.symlink_to(target)
            return SetupStep(name=name, status="applied", detail=f"created {path.name} -> {target}")
        return SetupStep(name=name, status="planned", detail=f"will create {path.name} -> {target}")
    if apply:
        path.unlink()
        path.symlink_to(target)
        return SetupStep(name=name, status="applied", detail=f"replaced {path.name} ({kind}) with symlink -> {target}")
    return SetupStep(name=name, status="planned", detail=f"will replace {path.name} ({kind}) with symlink -> {target}")


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
        print("dry-run: pass --apply to run local element install commands")
    for step in steps:
        print(f"[{step.status}] {step.name}: {step.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
