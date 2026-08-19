"""m4 development baseline capture (plan Step 1 / task T1).

Bootstraps and records the m4 starting state: verifies the declared dev
extra and pinned Python/Node toolchain, runs the pre-change selectors
(v10 contract, writer/UoW, timeline repository, media pipeline, bridge
server), and retains schema-versioned evidence at
``artifacts/m4/baseline.json`` containing the git SHA, tool versions,
per-selector pass/fail, and timestamps.

The baseline fails closed:

* any selector failure, collection error, or crashed lane makes the
  overall result ``ok: false`` and exits non-zero;
* any required tool (a pinned Python dev-extra distribution, Node, npm,
  or git) that is missing or below the pinned floor also exits non-zero;
* the script re-reads and validates the written baseline before exiting
  0, so an absent, truncated, or malformed baseline can never pass;
* ``--check-only`` validates an existing baseline without re-running the
  selectors and exits non-zero when the retained evidence is absent,
  malformed, or records any failure.

Every lane runs through pytest with ``--junit-xml``; per-lane logs and
JUnit XML are retained next to the baseline under ``artifacts/m4/`` so
passes and failures alike stay inspectable.

Usage::

    python3 scripts/reshape/m4_baseline.py [--out PATH] [--python PY]
        [--selectors v10_contract,writer_uow,...] [--check-only]

Exit status is 0 only when every selected lane passed and the retained
baseline was written and re-validated.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]

BASELINE_SCHEMA = "astrid.m4_baseline.v1"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "m4" / "baseline.json"

# The pre-change m4 selectors (plan Step 1): v10 contract, writer/UoW,
# timeline repository, media pipeline, and bridge server lanes. Lanes select
# whole test files (never individual functions) so no regression inside a
# file can hide behind a narrow node selection.
SELECTORS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("v10_contract", ("tests/v10/test_catalog_migrations.py",)),
    ("writer_uow", ("tests/v10/test_writer_uow.py",)),
    ("timeline_repository", ("tests/v10/test_timeline_repository.py",)),
    ("media_pipeline", ("tests/v10/test_media_pipeline.py",)),
    ("bridge_server", ("tests/integrations/reigh/test_local_bridge_server.py",)),
)

# Pinned Python dev-extra distributions the baseline must find installed.
# The m4 platform matrix freezes CPython 3.11/3.12 with an editable
# installation of the dev extra (see pyproject.toml [project.optional-dependencies].dev).
REQUIRED_PYTHON_PACKAGES: tuple[str, ...] = (
    "astrid",
    "pytest",
    "pytest-cov",
    "pytest-timeout",
    "mypy",
    "ruff",
    "jsonschema",
    "referencing",
    "build",
)

# Pinned Node floor from the m4 matrix (Linux CI / Node 20.19 / current
# Chromium). The local toolchain must satisfy it for the baseline to pass.
NODE_FLOOR = (20, 19, 0)

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?")


def _utc_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _tool_version(name: str) -> str:
    """Return the installed distribution version, or ``<missing>``."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "<missing>"


def _parse_node_version(raw: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.match(raw.strip())
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return (major, minor, patch)


@dataclass(frozen=True)
class Lane:
    """One pre-change m4 selector lane."""

    name: str
    selectors: tuple[str, ...]


@dataclass(frozen=True)
class LaneResult:
    """Durable outcome of one lane run, including its evidence paths."""

    name: str
    selectors: tuple[str, ...]
    passed: int
    failed: int
    skipped: int
    status: str
    returncode: int
    duration_seconds: float
    log: str
    junit: str

    def as_dict(self) -> dict[str, object]:
        return {
            "selectors": list(self.selectors),
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "status": self.status,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 3),
            "log": self.log,
            "junit": self.junit,
        }


def _parse_junit(junit_path: Path) -> tuple[int, int, int]:
    """Return ``(passed, failed, skipped)`` from a JUnit XML file."""
    tree = ET.parse(junit_path)
    root = tree.getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return 0, 0, 0
    tests = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    # JUnit's ``tests`` count includes skipped cases; passed is what remains
    # (the same rule s1_gate.py and run_ci_checks.sh use for lane counts).
    return tests - failures - errors - skipped, failures + errors, skipped


def _lane_status(passed: int, failed: int, skipped: int) -> str:
    if failed > 0:
        return "fail"
    if passed == 0 and skipped > 0:
        return "skip"
    return "pass"


def _run_lane(
    lane: Lane,
    *,
    python: str,
    repo_root: Path,
    evidence_dir: Path,
) -> LaneResult:
    """Run one lane's pytest selection and record its durable evidence."""
    junit_path = evidence_dir / f"{lane.name}-junit.xml"
    log_path = evidence_dir / f"{lane.name}.log"
    argv = [
        python,
        "-m",
        "pytest",
        *lane.selectors,
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        "--junit-xml",
        str(junit_path),
    ]
    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    duration_seconds = time.monotonic() - started
    log_path.write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    if junit_path.exists():
        passed, failed, skipped = _parse_junit(junit_path)
    else:
        # pytest itself crashed before writing JUnit XML (e.g. a collection
        # error); fall back to the exit code like s1_gate.py does.
        if completed.returncode == 0:
            passed, failed, skipped = 1, 0, 0
        else:
            passed, failed, skipped = 0, 1, 0
    return LaneResult(
        name=lane.name,
        selectors=lane.selectors,
        passed=passed,
        failed=failed,
        skipped=skipped,
        status=_lane_status(passed, failed, skipped),
        returncode=completed.returncode,
        duration_seconds=duration_seconds,
        log=str(log_path.relative_to(repo_root)),
        junit=str(junit_path.relative_to(repo_root)),
    )


def _collect_tools(python: str, repo_root: Path) -> tuple[dict[str, object], list[str]]:
    """Collect tool versions; return ``(tools, problems)``.

    Problems are non-empty when any required tool is missing or below the
    pinned floor; the caller must then fail closed.
    """
    problems: list[str] = []

    python_version = "<unknown>"
    try:
        completed = subprocess.run(
            [python, "--version"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        python_version = (
            completed.stdout.strip() or completed.stderr.strip()
        ) or "<unknown>"
    except OSError as exc:  # pragma: no cover - interpreter vanished
        problems.append(f"python interpreter {python!r} unavailable: {exc}")

    packages: dict[str, str] = {}
    for name in REQUIRED_PYTHON_PACKAGES:
        version = _tool_version(name)
        packages[name] = version
        if version == "<missing>":
            problems.append(f"required python package {name!r} is not installed")

    node_version = "<missing>"
    npm_version = "<missing>"
    for binary, key in (("node", "node"), ("npm", "npm")):
        try:
            completed = subprocess.run(
                [binary, "--version"],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )
            raw = (
                completed.stdout.strip() or completed.stderr.strip()
            )
        except OSError:
            raw = ""
        if raw:
            if key == "node":
                node_version = raw
            else:
                npm_version = raw
        else:
            problems.append(f"required tool {binary!r} is missing")
    if node_version != "<missing>":
        parsed = _parse_node_version(node_version)
        if parsed is None:
            problems.append(
                f"node version {node_version!r} is not semver-parseable"
            )
        elif parsed < NODE_FLOOR:
            problems.append(
                f"node {node_version} is below the pinned floor "
                f"{'.'.join(str(p) for p in NODE_FLOOR)}"
            )

    tools: dict[str, object] = {
        "python": {
            "executable": python,
            "version": python_version,
        },
        "python_packages": dict(sorted(packages.items())),
        "node": node_version,
        "npm": npm_version,
    }
    return tools, problems


def _git_sha(repo_root: Path) -> str:
    """Return the repository HEAD SHA, or raise on a non-git checkout."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "cannot resolve git HEAD SHA "
            f"(exit {completed.returncode}): {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _build_baseline(
    *,
    tools: dict[str, object],
    git_sha: str,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    results: Mapping[str, LaneResult],
    problems: Sequence[str],
    out: Path,
) -> dict[str, object]:
    """Compose the schema-versioned baseline document."""
    ok = not problems and all(
        result.status != "fail" for result in results.values()
    )
    selectors = {
        name: result.as_dict() for name, result in sorted(results.items())
    }
    baseline: dict[str, object] = {
        "schema": BASELINE_SCHEMA,
        "timestamp": {
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "repo": {
            "root": str(REPO_ROOT),
            "git_sha": git_sha,
            "git_short_sha": git_sha[:12],
        },
        "tools": tools,
        "selectors": selectors,
        "problems": list(problems),
        "ok": ok,
        "exit": 0 if ok else 1,
        "duration_seconds": round(duration_seconds, 3),
        "baseline_path": str(out.relative_to(REPO_ROOT)),
    }
    return baseline


def _validate_baseline(data: object) -> list[str]:
    """Validate a parsed baseline document; return a list of problems."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["baseline is not a JSON object"]
    if data.get("schema") != BASELINE_SCHEMA:
        errors.append(
            f"baseline schema {data.get('schema')!r} != {BASELINE_SCHEMA!r}"
        )
    repo = data.get("repo")
    if not isinstance(repo, dict) or not repo.get("git_sha"):
        errors.append("baseline missing repo.git_sha")
    tools = data.get("tools")
    if not isinstance(tools, dict):
        errors.append("baseline missing tools")
    else:
        packages = tools.get("python_packages")
        if not isinstance(packages, dict):
            errors.append("baseline missing tools.python_packages")
        else:
            for name in REQUIRED_PYTHON_PACKAGES:
                if packages.get(name) in (None, "<missing>"):
                    errors.append(
                        f"baseline missing required tool version for {name!r}"
                    )
        if tools.get("node") in (None, "<missing>"):
            errors.append("baseline missing node version")
        if tools.get("npm") in (None, "<missing>"):
            errors.append("baseline missing npm version")
    selectors = data.get("selectors")
    if not isinstance(selectors, dict):
        errors.append("baseline missing selectors")
    else:
        for name, _selectors in SELECTORS:
            entry = selectors.get(name)
            if not isinstance(entry, dict):
                errors.append(f"baseline missing selector lane {name!r}")
                continue
            if entry.get("status") not in ("pass", "fail", "skip"):
                errors.append(f"selector lane {name!r} has no valid status")
    if not isinstance(data.get("ok"), bool):
        errors.append("baseline missing boolean ok")
    timestamp = data.get("timestamp")
    if not isinstance(timestamp, dict) or not timestamp.get("finished_at"):
        errors.append("baseline missing timestamp.finished_at")
    return errors


def run_baseline(
    *,
    out: Path | None = None,
    python: str | None = None,
    selectors: Sequence[str] | None = None,
) -> tuple[dict[str, object], int]:
    """Run the pre-change selectors and retain schema-versioned evidence."""
    python_bin = python or sys.executable
    out_path = (out or DEFAULT_OUT).expanduser().resolve()
    evidence_dir = out_path.parent
    evidence_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_timestamp()
    started = time.monotonic()

    try:
        git_sha = _git_sha(REPO_ROOT)
    except RuntimeError as exc:
        # A failed baseline must fail closed: retain the failure evidence.
        baseline = _build_baseline(
            tools={"python": {"executable": python_bin, "version": "<unknown>"}},
            git_sha="<unavailable>",
            started_at=started_at,
            finished_at=_utc_timestamp(),
            duration_seconds=time.monotonic() - started,
            results={},
            problems=[str(exc)],
            out=out_path,
        )
        _write_atomic(out_path, baseline)
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"baseline={out_path} ok=false exit=1")
        return baseline, 1

    tools, problems = _collect_tools(python_bin, REPO_ROOT)
    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)

    lane_names = selectors or [name for name, _ in SELECTORS]
    by_name = {name: Lane(name, tuple(paths)) for name, paths in SELECTORS}
    unknown = [name for name in lane_names if name not in by_name]
    if unknown:
        problems.append(
            f"unknown selector lane(s) {', '.join(unknown)!r}; "
            f"choose from {', '.join(by_name)}"
        )
        lane_names = [name for name in lane_names if name in by_name]

    results: dict[str, LaneResult] = {}
    for name in lane_names:
        lane = by_name[name]
        print(f"=== lane {lane.name}: {' '.join(lane.selectors)} ===")
        result = _run_lane(
            lane,
            python=python_bin,
            repo_root=REPO_ROOT,
            evidence_dir=evidence_dir,
        )
        results[name] = result
        print(
            f"=== lane {lane.name}: {result.status} "
            f"({result.passed} passed, {result.failed} failed, "
            f"{result.skipped} skipped) in {result.duration_seconds:.2f}s "
            f"(exit {result.returncode}) ==="
        )

    duration_seconds = time.monotonic() - started
    baseline = _build_baseline(
        tools=tools,
        git_sha=git_sha,
        started_at=started_at,
        finished_at=_utc_timestamp(),
        duration_seconds=duration_seconds,
        results=results,
        problems=problems,
        out=out_path,
    )
    _write_atomic(out_path, baseline)

    # Fail closed on absent/malformed retained evidence: re-read and validate
    # the exact bytes that will be consumed by later steps.
    validation_errors = _validate_baseline(
        json.loads(out_path.read_text(encoding="utf-8"))
    )
    for error in validation_errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if validation_errors:
        baseline["ok"] = False
        baseline["exit"] = 1
        _write_atomic(out_path, baseline)

    ok = bool(baseline["ok"]) and not validation_errors
    exit_code = 0 if ok else 1
    print(f"ok={str(ok).lower()} exit={exit_code}")
    print(f"baseline={out_path}")
    return baseline, exit_code


def _write_atomic(path: Path, data: dict[str, object]) -> None:
    """Write the baseline atomically so a hard kill never leaves a truncation."""
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def check_baseline(out: Path | None = None) -> tuple[dict[str, object], int]:
    """Validate an existing retained baseline without re-running selectors."""
    out_path = (out or DEFAULT_OUT).expanduser().resolve()
    if not out_path.exists():
        print(
            f"ERROR: baseline absent at {out_path}; "
            "run 'make m4-baseline' first",
            file=sys.stderr,
        )
        return {}, 1
    data = json.loads(out_path.read_text(encoding="utf-8"))
    errors = _validate_baseline(data)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    ok = bool(data.get("ok")) and not errors
    print(f"ok={str(ok).lower()} exit={0 if ok else 1}")
    print(f"baseline={out_path}")
    return data, 0 if ok else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the pre-change m4 selector lanes after dependency bootstrap "
            "and retain schema-versioned evidence at artifacts/m4/baseline.json."
        )
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Baseline evidence path (default: artifacts/m4/baseline.json).",
    )
    parser.add_argument(
        "--python",
        help="Interpreter used for lane subprocesses (default: sys.executable).",
    )
    parser.add_argument(
        "--selectors",
        help=(
            "Comma-separated lane subset to run "
            "(default: all five pre-change lanes)."
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate an existing baseline without re-running selectors.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.check_only:
        _data, exit_code = check_baseline(args.out)
        return exit_code
    selectors = None
    if args.selectors:
        selectors = tuple(
            raw.strip() for raw in args.selectors.split(",") if raw.strip()
        )
    _data, exit_code = run_baseline(
        out=args.out,
        python=args.python,
        selectors=selectors,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
