"""Validate hashed dependency locks and record the release gate toolchain."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATHS = (
    Path("requirements/build.lock"),
    Path("requirements/runtime.lock"),
)
HASH_RE = re.compile(r"--hash=sha256:[0-9a-f]{64}(?:\s|$)")
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^ ;\\]+)")


class ReproducibilityError(RuntimeError):
    """A required lock or release tool is absent, ambiguous, or unpinned."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _lock_blocks(path: Path) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace():
            if not current:
                raise ReproducibilityError(f"orphan continuation in {path}: {line!r}")
            current.append(stripped)
            continue
        if current:
            blocks.append(" ".join(current))
        current = [stripped]
    if current:
        blocks.append(" ".join(current))
    return blocks


def validate_hashed_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReproducibilityError(f"required dependency lock is missing: {path}")
    pins: dict[str, set[str]] = {}
    for block in _lock_blocks(path):
        match = PIN_RE.match(block)
        if match is None:
            raise ReproducibilityError(f"lock entry is not an exact == pin: {block!r}")
        if HASH_RE.search(block) is None:
            raise ReproducibilityError(f"lock entry has no sha256 hash: {block!r}")
        name = _normalise(match.group(1))
        pins.setdefault(name, set()).add(match.group(2))
    if not pins:
        raise ReproducibilityError(f"dependency lock is empty: {path}")
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "packages": len(pins),
        "pins": {name: sorted(versions) for name, versions in pins.items()},
    }


def validate_dependency_locks(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    root = repo_root.resolve()
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    reports = {
        str(relative): validate_hashed_lock(root / relative) for relative in LOCK_PATHS
    }
    for relative, report in reports.items():
        report["path"] = relative
    build_pins = reports[str(LOCK_PATHS[0])]["pins"]
    runtime_pins = reports[str(LOCK_PATHS[1])]["pins"]

    build_requirements = pyproject["build-system"]["requires"]
    for requirement in build_requirements:
        match = PIN_RE.match(requirement)
        if match is None:
            raise ReproducibilityError(
                f"pyproject build requirement is not exactly pinned: {requirement!r}"
            )
        name = _normalise(match.group(1))
        if match.group(2) not in build_pins.get(name, []):
            raise ReproducibilityError(
                f"build lock does not match pyproject pin {name}=={match.group(2)}"
            )

    for requirement in pyproject["project"]["dependencies"]:
        name_match = re.match(r"^([A-Za-z0-9_.-]+)", requirement)
        if name_match is None or _normalise(name_match.group(1)) not in runtime_pins:
            raise ReproducibilityError(
                f"runtime lock does not cover direct dependency: {requirement!r}"
            )
    for report in reports.values():
        report.pop("pins")
    return {"schema": "astrid.dependency_locks.v1", "locks": reports}


def _tool(name: str, command: Sequence[str]) -> dict[str, str]:
    executable = shutil.which(command[0])
    if executable is None:
        raise ReproducibilityError(f"required release tool is missing: {name}")
    result = subprocess.run(
        [executable, *command[1:]],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0 or not output:
        raise ReproducibilityError(
            f"required release tool {name} could not report a version (exit {result.returncode})"
        )
    return {"executable": str(Path(executable).resolve()), "version": output.splitlines()[0]}


def validate_playwright(root: Path) -> dict[str, Any]:
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    declared = package["devDependencies"]["playwright"]
    locked = lock["packages"]["node_modules/playwright"]["version"]
    core = lock["packages"]["node_modules/playwright-core"]["version"]
    if declared != locked or core != locked:
        raise ReproducibilityError(
            f"Playwright must be exact and lock-aligned: declared={declared!r}, "
            f"playwright={locked!r}, core={core!r}"
        )
    report: dict[str, Any] = {
        "package_version": locked,
        "package_lock_sha256": _sha256(root / "package-lock.json"),
    }
    browsers = root / "node_modules" / "playwright-core" / "browsers.json"
    if browsers.is_file():
        data = json.loads(browsers.read_text(encoding="utf-8"))
        chromium = next(
            (item for item in data["browsers"] if item["name"] == "chromium"), None
        )
        if chromium is None:
            raise ReproducibilityError("installed Playwright has no Chromium revision")
        report["chromium"] = {
            key: chromium.get(key)
            for key in ("revision", "browserVersion", "installByDefault")
        }
    return report


def record_required_toolchain(
    *,
    repo_root: Path = REPO_ROOT,
    expected_python: str | None = None,
    playwright_root: Path | None = None,
) -> dict[str, Any]:
    python_version = platform.python_version()
    if expected_python is not None and not (
        python_version == expected_python or python_version.startswith(expected_python + ".")
    ):
        raise ReproducibilityError(
            f"Python mismatch: expected {expected_python}, observed {python_version}"
        )
    report: dict[str, Any] = {
        "schema": "astrid.release_toolchain.v1",
        "python": {
            "executable": str(Path(sys.executable).resolve()),
            "version": python_version,
            "implementation": platform.python_implementation(),
        },
        "tools": {
            "make": _tool("make", ("make", "--version")),
            "bash": _tool("bash", ("bash", "--version")),
            "git": _tool("git", ("git", "--version")),
            "ffmpeg": _tool("ffmpeg", ("ffmpeg", "-version")),
            "ffprobe": _tool("ffprobe", ("ffprobe", "-version")),
        },
        "dependencies": validate_dependency_locks(repo_root),
    }
    if playwright_root is not None:
        report["playwright"] = validate_playwright(playwright_root.resolve())
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release_reproducibility")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--expected-python")
    parser.add_argument("--playwright-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = record_required_toolchain(
        repo_root=args.repo_root,
        expected_python=args.expected_python,
        playwright_root=args.playwright_root,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
