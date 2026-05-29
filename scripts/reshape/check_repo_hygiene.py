"""Guard against generated root artifacts and tracked ignored outputs."""

from __future__ import annotations

from collections.abc import Iterable
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

TRACKED_PATH_ALLOWLISTS = (
    ".env.example",
    "astrid/core/util/secrets.py",
    "docs/assets/astrid-orchestration.png",
    "tests/**/fixtures/**",
    "tests/fixtures/**",
)

TRACKED_PATH_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "local env filename",
        (
            ".env",
            ".env.*",
            "this.env",
            "*/.env",
            "*/.env.*",
            "*/this.env",
        ),
    ),
    (
        "credential-like filename",
        (
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
            "*credentials*",
            "*secret*",
        ),
    ),
    (
        "generated runtime directory",
        (
            "runs/*",
            "*/runs/*",
            "out/*",
            "*/out/*",
            "cache/*",
            "*/cache/*",
            ".astrid/*",
            "*/.astrid/*",
            "tests/agentic/reports/*",
            "astrid/packs/*/build/*",
            "examples/packs/*/build/*",
        ),
    ),
    (
        "tracked runtime media output",
        (
            "*.mp4",
            "*.mov",
            "*.wav",
            "*.jpg",
            "*.jpeg",
            "*.png",
        ),
    ),
    (
        "local tool state",
        (
            ".desloppify",
            ".desloppify/*",
            ".desloppify/**",
            "*/.desloppify",
            "*/.desloppify/*",
            "*/.desloppify/**",
            "*.bak",
        ),
    ),
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


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _is_allowlisted(path: str) -> bool:
    return _matches_any(path, TRACKED_PATH_ALLOWLISTS)


def find_root_generated_artifacts() -> list[str]:
    findings: list[str] = []
    for pattern in ROOT_GENERATED_PATTERNS:
        findings.extend(path.name for path in REPO_ROOT.glob(pattern) if path.is_file())
    return sorted(set(findings))


def classify_tracked_path(path: str) -> list[str]:
    if _is_allowlisted(path):
        return []
    return [label for label, patterns in TRACKED_PATH_RULES if _matches_any(path, patterns)]


def find_tracked_ignored_artifacts() -> list[tuple[str, str]]:
    findings: set[tuple[str, str]] = set()
    for tracked in _tracked_files():
        if not (REPO_ROOT / tracked).exists():
            continue
        for category in classify_tracked_path(tracked):
            findings.add((category, tracked))
    return sorted(findings, key=lambda item: (item[1], item[0]))


def main() -> int:
    failed = False
    root_findings = find_root_generated_artifacts()
    if root_findings:
        failed = True
        print("root generated artifacts must not be committed or kept at repository root:", file=sys.stderr)
        for path in root_findings:
            print(f"  [root generated artifact] {path}", file=sys.stderr)

    tracked_findings = find_tracked_ignored_artifacts()
    if tracked_findings:
        failed = True
        print("tracked ignored artifacts must not be committed:", file=sys.stderr)
        for category, path in tracked_findings:
            print(f"  [{category}] {path}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
