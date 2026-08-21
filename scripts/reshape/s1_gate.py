"""One-command S1 gate runner for the m1 event-core foundation.

Plan Step 23 (task T42): a fresh-root gate script that selects the
manifest, catalog, migration, registry, receipt, replay, crash,
contention, conformance, lint, bridge, and provider lanes, runs them
hermetically against a fresh temp root, and emits durable machine-readable
evidence: a JSON summary plus per-lane logs and JUnit XML.

The gate deliberately selects only the twelve focused lane suites; it never
re-runs the broad default pytest suite, which the harness owns.

Usage::

    python3 scripts/reshape/s1_gate.py [--out-dir DIR] [--work-dir DIR]
        [--python PY] [--lanes manifest,catalog,...]

Exit status is 0 when every selected lane passes (skips are not failures)
and 1 otherwise; the summary and every log are retained in both cases so
CI can upload passes and failures alike.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]

SUMMARY_SCHEMA = "astrid.s1_gate.summary.v1"

# Environment names scrubbed from the child environment so an ambient task
# session can never leak into the hermetic lane runs (mirrors the Sprint 0
# migration-gate scrub list).
_SCRUB_ENV_PREFIXES = ("ASTRID_TASK_",)
_SCRUB_ENV_NAMES = frozenset(
    {
        "ASTRID_SESSION_ID",
        "ASTRID_PROJECT",
        "ASTRID_PROJECT_SLUG",
        "ASTRID_PROJECT_RUN",
        "ASTRID_CURRENT_RUN",
        "ASTRID_CURRENT_SESSION",
        "ASTRID_ATTACHED_SESSION",
    }
)


@dataclass(frozen=True)
class Lane:
    """One focused S1 lane: a name plus the test selectors that prove it."""

    name: str
    selectors: tuple[str, ...]


# The twelve focused S1 lanes. A lane selects whole test files (never
# individual test functions), and files may be shared across lanes because
# one file often proves several plan dimensions (e.g. test_registry.py
# carries both the strict 11-field manifest contract and the frozen
# registry composition). Every lane is reported independently in the
# summary so each dimension has its own retained evidence.
LANES: tuple[Lane, ...] = (
    Lane("manifest", ("tests/v10/test_registry.py",)),
    Lane("catalog", ("tests/v10/test_catalog_migrations.py",)),
    Lane("migration", ("tests/v10/test_catalog_migrations.py",)),
    Lane("registry", ("tests/v10/test_registry.py",)),
    Lane("receipt", ("tests/v10/test_receipts_events.py",)),
    Lane("replay", ("tests/v10/test_receipts_events.py",)),
    Lane("crash", ("tests/v10/test_crash_atomicity.py",)),
    Lane("contention", ("tests/v10/test_contention.py",)),
    Lane("conformance", ("tests/v10/test_conformance.py",)),
    Lane(
        "lint",
        ("tests/v10/test_authority_lint.py", "tests/test_structure_contracts.py"),
    ),
    Lane("bridge", ("tests/integrations/reigh/test_local_bridge_server.py",)),
    Lane("provider", ("tests/integrations/reigh/test_repository_provider.py",)),
)


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


@dataclass(frozen=True)
class GateSummary:
    """Machine-readable summary persisted to ``s1-summary.json``."""

    schema: str
    timestamp: str
    repo_root: str
    work_dir: str
    python: str
    env: dict[str, str]
    out_dir: str
    ok: bool
    exit: int
    duration_seconds: float
    lanes: dict[str, LaneResult]
    artifacts: dict[str, str]

    def as_json(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "timestamp": self.timestamp,
            "repo_root": self.repo_root,
            "work_dir": self.work_dir,
            "python": self.python,
            "env": dict(sorted(self.env.items())),
            "out_dir": self.out_dir,
            "ok": self.ok,
            "exit": self.exit,
            "duration_seconds": round(self.duration_seconds, 3),
            "lanes": {
                name: result.as_dict()
                for name, result in self.lanes.items()
            },
            "artifacts": dict(sorted(self.artifacts.items())),
        }


def _utc_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _default_out_dir(repo_root: Path) -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%d-%H%M%S"
    )
    return repo_root / ".s1-gate" / stamp


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
    # (the same SD1 rule run_ci_checks.sh uses for its lane counts).
    return tests - failures - errors - skipped, failures + errors, skipped


def _lane_status(passed: int, failed: int, skipped: int) -> str:
    if failed > 0:
        return "fail"
    if passed == 0 and skipped > 0:
        return "skip"
    return "pass"


def _child_env(repo_root: Path, work_dir: Path) -> dict[str, str]:
    """Build the fresh hermetic environment shared by every lane run."""
    projects_root = work_dir / "projects"
    home_dir = work_dir / "home"
    projects_root.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in _SCRUB_ENV_NAMES
        and not key.startswith(_SCRUB_ENV_PREFIXES)
    }
    env["ASTRID_PROJECTS_ROOT"] = str(projects_root)
    env["ASTRID_HOME"] = str(home_dir)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )
    return env


def _run_lane(
    lane: Lane,
    *,
    python: str,
    repo_root: Path,
    env: dict[str, str],
    out_dir: Path,
) -> LaneResult:
    """Run one lane's pytest selection and record its durable evidence."""
    junit_path = out_dir / f"{lane.name}-junit.xml"
    log_path = out_dir / f"{lane.name}.log"
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
        env=env,
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
        # pytest itself crashed before writing JUnit XML (e.g. collection
        # error); fall back to the exit code like run_ci_checks.sh does.
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
        log=str(log_path.resolve()),
        junit=str(junit_path.resolve()),
    )


def run_gate(
    *,
    lanes: Sequence[Lane] = LANES,
    out_dir: Path | None = None,
    work_dir: Path | None = None,
    python: str | None = None,
) -> GateSummary:
    """Run the selected S1 lanes against a fresh root and write the summary.

    Every lane runs in a fresh hermetic root (``ASTRID_PROJECTS_ROOT`` and
    ``ASTRID_HOME`` under ``work_dir``) so ambient state can never leak in.
    The machine-readable summary plus every lane log and JUnit XML are
    written under ``out_dir`` and retained even when lanes fail, so CI can
    upload passes and failures alike.
    """
    repo_root = REPO_ROOT
    python_bin = python or sys.executable
    out = (out_dir or _default_out_dir(repo_root)).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    root = (work_dir or Path(tempfile.mkdtemp(prefix="astrid-s1-gate-"))).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    env = _child_env(repo_root, root)

    gate_log_path = out / "s1-gate.log"
    gate_log_lines: list[str] = []
    results: dict[str, LaneResult] = {}
    started = time.monotonic()
    for lane in lanes:
        gate_log_lines.append(
            f"=== lane {lane.name}: {' '.join(lane.selectors)} ==="
        )
        result = _run_lane(
            lane,
            python=python_bin,
            repo_root=repo_root,
            env=env,
            out_dir=out,
        )
        results[lane.name] = result
        gate_log_lines.append(
            f"=== lane {lane.name}: {result.status} "
            f"({result.passed} passed, {result.failed} failed, "
            f"{result.skipped} skipped) in {result.duration_seconds:.2f}s "
            f"(exit {result.returncode}) ==="
        )
    duration_seconds = time.monotonic() - started

    ok = all(result.status != "fail" for result in results.values())
    summary_path = out / "s1-summary.json"
    summary = GateSummary(
        schema=SUMMARY_SCHEMA,
        timestamp=_utc_timestamp(),
        repo_root=str(repo_root),
        work_dir=str(root),
        python=python_bin,
        env={
            "ASTRID_PROJECTS_ROOT": env["ASTRID_PROJECTS_ROOT"],
            "ASTRID_HOME": env["ASTRID_HOME"],
        },
        out_dir=str(out),
        ok=ok,
        exit=0 if ok else 1,
        duration_seconds=duration_seconds,
        lanes=results,
        artifacts={
            "summary": str(summary_path.resolve()),
            "gate_log": str(gate_log_path.resolve()),
            "out_dir": str(out),
        },
    )
    gate_log_lines.extend(
        [
            f"=== gate: {'PASS' if ok else 'FAIL'} in "
            f"{duration_seconds:.2f}s (exit {summary.exit}) ===",
            f"summary={summary.artifacts['summary']}",
            f"work_dir={summary.work_dir}",
        ]
    )
    gate_log_path.write_text(
        "\n".join(gate_log_lines) + "\n", encoding="utf-8"
    )

    # Write atomically so a hard kill never leaves a truncated summary.
    tmp_summary_path = out / "s1-summary.json.tmp"
    tmp_summary_path.write_text(
        json.dumps(summary.as_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_summary_path, summary_path)
    return summary


def _select_lanes(names: str | None) -> tuple[Lane, ...]:
    """Resolve a comma-separated CLI lane subset to lane definitions."""
    if not names:
        return LANES
    by_name = {lane.name: lane for lane in LANES}
    selected: list[Lane] = []
    for raw in names.split(","):
        name = raw.strip()
        if name not in by_name:
            raise SystemExit(
                "ERROR: unknown S1 lane "
                f"{name!r}; choose from {', '.join(by_name)}"
            )
        selected.append(by_name[name])
    return tuple(selected)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the focused m1 S1 gate lanes against a fresh hermetic root "
            "and emit a durable JSON summary plus per-lane logs."
        )
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help=(
            "Where to write s1-summary.json, s1-gate.log, and per-lane "
            "evidence (default: <repo>/.s1-gate/<utc-timestamp>)."
        ),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help=(
            "Fresh root for ASTRID_PROJECTS_ROOT/ASTRID_HOME "
            "(default: a new temp directory)."
        ),
    )
    parser.add_argument(
        "--python",
        help="Interpreter used for lane subprocesses (default: sys.executable).",
    )
    parser.add_argument(
        "--lanes",
        help="Comma-separated lane subset to run (default: all twelve lanes).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = run_gate(
        lanes=_select_lanes(args.lanes),
        out_dir=args.out_dir,
        work_dir=args.work_dir,
        python=args.python,
    )
    for name, result in summary.lanes.items():
        print(
            f"lane {name}: {result.status} "
            f"({result.passed} passed, {result.failed} failed, "
            f"{result.skipped} skipped) - log {result.log}"
        )
    print(f"ok={str(summary.ok).lower()} exit={summary.exit}")
    print(f"summary={summary.artifacts['summary']}")
    print(f"gate_log={summary.artifacts['gate_log']}")
    print(f"work_dir={summary.work_dir}")
    return summary.exit


if __name__ == "__main__":
    raise SystemExit(main())
