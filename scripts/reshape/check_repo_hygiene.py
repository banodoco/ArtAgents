"""Guard against generated root artifacts and tracked ignored outputs."""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ROOT_GENERATED_PATTERNS = (
    "agentic-*.report.md",
    "dry_run_map.json",
    "M5_TEST_STATUS.md",
    "plan_v1.revised.md",
    "report-*.md",
)

TRACKED_IGNORED_PATTERNS = (
    ".desloppify",
    ".desloppify/*",
    ".desloppify/**",
    "*/.desloppify",
    "*/.desloppify/*",
    "*/.desloppify/**",
    "*.bak",
)


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


def find_tracked_ignored_artifacts() -> list[str]:
    findings: list[str] = []
    for tracked in _tracked_files():
        if not (REPO_ROOT / tracked).exists():
            continue
        if any(fnmatch.fnmatch(tracked, pattern) for pattern in TRACKED_IGNORED_PATTERNS):
            findings.append(tracked)
    return sorted(findings)


def main() -> int:
    failures = {
        "root generated artifacts": find_root_generated_artifacts(),
        "tracked ignored artifacts": find_tracked_ignored_artifacts(),
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
