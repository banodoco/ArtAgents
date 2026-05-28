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
    steps.append(_plan_agents_symlink(root, apply=apply))

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


def _plan_agents_symlink(root: Path, *, apply: bool) -> SetupStep:
    """Ensure AGENTS.md points directly at the core skill source."""
    agents = root / "AGENTS.md"
    target = Path("astrid") / "packs" / "_core" / "skill" / "SKILL.md"
    skill = root / target
    if not skill.is_file():
        return SetupStep(name="agents.md symlink", status="warn", detail=f"{skill} missing; cannot link AGENTS.md")
    target_text = target.as_posix()
    if agents.is_symlink() and (root / agents.readlink()).resolve() == skill.resolve():
        if agents.readlink().as_posix() == target_text:
            return SetupStep(name="agents.md symlink", status="ok", detail=f"AGENTS.md -> {target_text}")
        status = "applied" if apply else "planned"
        detail = f"{'updated' if apply else 'will update'} AGENTS.md -> {target_text}"
        if apply:
            agents.unlink()
            agents.symlink_to(target_text)
        return SetupStep(name="agents.md symlink", status=status, detail=detail)
    if agents.is_symlink() and not (root / agents.readlink()).exists():
        kind = "broken symlink"
    elif agents.is_symlink():
        kind = "wrong symlink"
    else:
        kind = "regular file"
    if not agents.exists() and not agents.is_symlink():
        if apply:
            agents.symlink_to(target_text)
            return SetupStep(name="agents.md symlink", status="applied", detail=f"created AGENTS.md -> {target_text}")
        return SetupStep(name="agents.md symlink", status="planned", detail=f"will create AGENTS.md -> {target_text}")
    if apply:
        agents.unlink()
        agents.symlink_to(target_text)
        return SetupStep(name="agents.md symlink", status="applied", detail=f"replaced AGENTS.md ({kind}) with symlink -> {target_text}")
    return SetupStep(name="agents.md symlink", status="planned", detail=f"will replace AGENTS.md ({kind}) with symlink -> {target_text}")


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
