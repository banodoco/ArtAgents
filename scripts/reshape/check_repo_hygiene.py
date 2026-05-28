"""Guard against generated root artifacts and tracked ignored outputs."""

from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ROOT_FILE_ALLOWLIST = {
    ".env.example",
    ".gitignore",
    ".python-version",
    "AGENTS.md",
    "LICENSE",
    "README.md",
    "SKILL.md",
    "package-lock.json",
    "package.json",
    "pyproject.toml",
    "pytest.ini",
    "requirements-dev.txt",
    "requirements.txt",
}

ROOT_DIR_ALLOWLIST = {
    ".github",
    "agents",
    "astrid",
    "docs",
    "examples",
    "fixtures",
    "remotion",
    "scripts",
    "tests",
}

ROOT_GENERATED_PATTERNS = (
    "agentic-*.report.md",
    "chain.yaml",
    "dry_run_map.json",
    "idea.md",
    "M5_TEST_STATUS.md",
    "plan_revision.json",
    "plan_v1.revised.md",
    "report-*.md",
    "scorecard.png",
)

TRACKED_IGNORED_PATTERNS = (
    ".DS_Store",
    "*/.DS_Store",
    ".compactify",
    ".compactify/*",
    ".compactify/**",
    ".desloppify",
    ".desloppify/*",
    ".desloppify/**",
    "*/.desloppify",
    "*/.desloppify/*",
    "*/.desloppify/**",
    ".venv",
    ".venv/*",
    ".venv/**",
    "node_modules",
    "node_modules/*",
    "node_modules/**",
    "*.bak",
    "*.preview.*",
    "*tmp_*",
    # Megaplan local state — must never be tracked; docs/megaplan/ is the
    # source-of-truth directory and is intentionally NOT ignored.
    ".megaplan",
    ".megaplan/*",
    ".megaplan/**",
    ".megaplan-agentic",
    ".megaplan-agentic/*",
    ".megaplan-agentic/**",
    # Astrid local runtime state
    ".astrid",
    ".astrid/*",
    ".astrid/**",
    # Generated project worktree roots
    "mgt-*",
    "mgt-*/**",
    "out",
    "out/*",
    "out/**",
    "runs",
    "runs/*",
    "runs/**",
)

ROOT_SKILL_SYMLINKS = {
    "AGENTS.md": Path("astrid") / "packs" / "_core" / "skill" / "SKILL.md",
    "SKILL.md": Path("astrid") / "packs" / "_core" / "skill" / "SKILL.md",
}


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def find_root_generated_artifacts() -> list[str]:
    findings: list[str] = []
    for pattern in ROOT_GENERATED_PATTERNS:
        findings.extend(path.name for path in REPO_ROOT.glob(pattern) if path.is_file())
    return sorted(set(findings))


def find_unknown_root_entries(tracked: list[str] | None = None) -> list[str]:
    findings: list[str] = []
    for path in tracked or _tracked_files():
        if "/" in path:
            root = path.split("/", 1)[0]
            if root not in ROOT_DIR_ALLOWLIST and (REPO_ROOT / path).exists():
                findings.append(root + "/")
            continue
        if path not in ROOT_FILE_ALLOWLIST and (REPO_ROOT / path).exists():
            findings.append(path)
    return sorted(set(findings))


def find_tracked_ignored_artifacts(tracked: list[str] | None = None) -> list[str]:
    findings: list[str] = []
    for path in tracked or _tracked_files():
        if not (REPO_ROOT / path).exists():
            continue
        if any(fnmatch.fnmatch(path, pattern) for pattern in TRACKED_IGNORED_PATTERNS):
            findings.append(path)
    return sorted(findings)


def find_root_skill_symlink_violations() -> list[str]:
    findings: list[str] = []
    for name, expected in ROOT_SKILL_SYMLINKS.items():
        path = REPO_ROOT / name
        if not path.is_symlink():
            findings.append(f"{name} must be a symlink to {expected.as_posix()}")
            continue
        link = Path(os.readlink(path))
        if link != expected:
            findings.append(f"{name} points to {link.as_posix()}, expected {expected.as_posix()}")
            continue
        if not (REPO_ROOT / link).is_file():
            findings.append(f"{name} points to missing target {link.as_posix()}")
    return sorted(findings)


def main() -> int:
    failures = {
        "unknown root entries": find_unknown_root_entries(),
        "root generated artifacts": find_root_generated_artifacts(),
        "tracked ignored artifacts": find_tracked_ignored_artifacts(),
        "root skill symlink violations": find_root_skill_symlink_violations(),
    }
    failed = False
    for label, paths in failures.items():
        if not paths:
            continue
        failed = True
        print(f"{label} must not be committed or kept at repository root:", file=sys.stderr)
        for path in paths:
            print(f"  {path}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
