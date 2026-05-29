"""Parallel agentic scenario runner — process-per-scenario with filesystem isolation.

Dispatches each scenario as its own subprocess (via the existing sequential
runner.py) with isolated ASTRID_HOME and ASTRID_PROJECTS_ROOT, captures
per-scenario stdout/stderr logs, and invokes pattern_finder after all
children complete.

Usage:
    python -m tests.agentic.parallel_runner --all --parallel 3
    python -m tests.agentic.parallel_runner specific_transcribe cold_restart_midrun --parallel 2
    python -m tests.agentic.parallel_runner --cleanup [--apply]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"

# Per-suite sandbox under $TMPDIR — never touches the developer's real ~/.astrid.
_SUITE_SANDBOX = Path(tempfile.gettempdir()) / "astrid-agentic-suite"


def _parallel_root(run_tag: str) -> Path:
    """Return /tmp/astrid-parallel-<tag>/."""
    return Path(f"/tmp/astrid-parallel-{run_tag}")

DEFAULT_PARALLEL = 3
DEFAULT_TIMEOUT = 1800  # 30 minutes


def _now_tag() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _discover_scenarios(scenario_names: list[str] | None) -> list[str]:
    """Return sorted scenario names. If scenario_names is None, discover all.
    Excludes _schema.yaml (globs *.yaml, filters files starting with '_').
    """
    if scenario_names:
        # Validate each name exists.
        for name in scenario_names:
            path = SCENARIOS_DIR / f"{name}.yaml"
            if not path.is_file():
                raise FileNotFoundError(f"scenario {name!r} not found at {path}")
        return scenario_names

    return sorted(
        p.stem
        for p in SCENARIOS_DIR.glob("*.yaml")
        if not p.name.startswith("_")
    )


def _run_one(
    scenario: str,
    run_tag: str,
    timeout: int,
) -> tuple[str, int, float, bool]:
    """Run a single scenario in an isolated subprocess.

    Returns (scenario, exit_code, elapsed_sec, timed_out).
    """
    base = _parallel_root(run_tag) / scenario
    home_dir = base / "home"
    projects_dir = base / "projects"
    logs_dir = base / "logs"
    home_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Seed identity.json so `astrid attach --as agent:<slug>` in scenario
    # priming doesn't trip the first-run interactive bootstrap (which fails
    # under a non-tty subprocess with "agent identity is not configured and
    # stdin is not interactive"). Prefer copying the user's existing
    # identity; otherwise synthesize a minimal valid record.
    isolated_identity = home_dir / "identity.json"
    if not isolated_identity.exists():
        source_identity = _SUITE_SANDBOX / "home" / "identity.json"
        if source_identity.is_file():
            shutil.copyfile(source_identity, isolated_identity)
        else:
            isolated_identity.write_text(
                json.dumps(
                    {
                        "agent_id": "agent-parallel-runner",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

    stdout_log = logs_dir / "stdout.log"
    stderr_log = logs_dir / "stderr.log"

    # Build isolated env: only ASTRID_HOME and ASTRID_PROJECTS_ROOT differ.
    child_env = dict(os.environ)
    child_env["ASTRID_HOME"] = str(home_dir)
    child_env["ASTRID_PROJECTS_ROOT"] = str(projects_dir)

    cmd = [
        sys.executable,
        "-m",
        "tests.agentic.runner",
        scenario,
        "--run-tag",
        run_tag,
    ]

    started = time.time()

    with open(stdout_log, "w", encoding="utf-8") as out_f, \
         open(stderr_log, "w", encoding="utf-8") as err_f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=child_env,
            stdout=out_f,
            stderr=err_f,
            # Start a new session so we can kill the process tree.
            start_new_session=True,
        )

        timed_out = False
        try:
            exit_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Kill the process tree: escalate SIGTERM → SIGKILL.
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)  # type: ignore[union-attr]
            except (ProcessLookupError, OSError):
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)  # type: ignore[union-attr]
                except (ProcessLookupError, OSError):
                    pass
                proc.wait(timeout=5)
            exit_code = -1

    elapsed = time.time() - started
    return scenario, exit_code, elapsed, timed_out


def _print_summary(
    results: list[tuple[str, int, float, bool]],
    run_tag: str,
    wall_start: float,
) -> None:
    """Print a summary table after all scenarios complete."""
    wall_elapsed = time.time() - wall_start
    total = len(results)
    passed = sum(1 for _, rc, _, to in results if rc == 0 and not to)
    timed_out_count = sum(1 for _, _, _, to in results if to)

    print(f"\n{run_tag} parallel dogfood: {passed}/{total} scenarios passed")
    for scenario, rc, elapsed, to in sorted(results, key=lambda r: r[0]):
        if to:
            symbol = "⏱"
            label = "timed out"
        elif rc == 0:
            symbol = "✓"
            label = f"passed, {elapsed:.0f}s"
        else:
            symbol = "✗"
            label = f"failed (rc={rc}), {elapsed:.0f}s"
        path_hint = f"{_parallel_root(run_tag) / scenario / 'logs' / ''}"
        print(f"  {symbol} {scenario} ({label}) — see {path_hint}")

    minutes = wall_elapsed / 60
    print(f"\ntotal wall-clock: {wall_elapsed:.0f}s (~{minutes:.1f} min)")


def _run_pattern_finder(run_tag: str) -> None:
    """Invoke pattern_finder on the combined results."""
    reports_dir = Path(__file__).resolve().parent / "reports"
    run_dir = reports_dir / run_tag
    if not run_dir.is_dir():
        print(f"pattern_finder: run dir {run_dir} does not exist, skipping",
              file=sys.stderr)
        return
    cmd = [
        sys.executable,
        "-m",
        "tests.agentic.pattern_finder",
        "--run-dir",
        str(run_dir),
    ]
    print(f"\ninvoking pattern_finder: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)


def _cleanup(tag: str | None, all_tags: bool, apply: bool) -> None:
    """Remove /tmp/astrid-parallel-<tag>/ directories."""
    if all_tags:
        targets = sorted(Path("/tmp").glob("astrid-parallel-*"))
    elif tag:
        targets = [Path(f"/tmp/astrid-parallel-{tag}")]
    else:
        print("cleanup: specify --tag, --all, or both", file=sys.stderr)
        return

    for t in targets:
        if not t.exists():
            print(f"cleanup: {t} does not exist (skip)")
            continue
        if apply:
            print(f"cleanup: removing {t}")
            shutil.rmtree(t)
        else:
            print(f"cleanup: would remove {t} (dry-run; use --apply)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tests.agentic.parallel_runner",
        description="Run agentic scenarios in parallel with per-scenario isolation.",
    )
    ap.add_argument(
        "scenarios", nargs="*",
        help="scenario name(s); omit with --all",
    )
    ap.add_argument(
        "--all", action="store_true",
        help="run every scenario under scenarios/",
    )
    ap.add_argument(
        "--parallel", type=int, default=DEFAULT_PARALLEL,
        help=f"max concurrent scenarios (default: {DEFAULT_PARALLEL})",
    )
    ap.add_argument(
        "--run-tag", default=None,
        help="prefix for report directory (default: YYYYMMDD-HHMMSS timestamp)",
    )
    ap.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"per-scenario timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    ap.add_argument(
        "--cleanup", action="store_true",
        help="remove /tmp/astrid-parallel-<tag> directories (dry-run unless --apply)",
    )
    ap.add_argument(
        "--apply", action="store_true",
        help="actually delete during --cleanup (default: dry-run)",
    )

    args = ap.parse_args(argv)

    # Cleanup mode.
    if args.cleanup:
        _cleanup(tag=args.run_tag, all_tags=args.all, apply=args.apply)
        return 0

    # Run mode.
    if not args.scenarios and not args.all:
        ap.error("specify scenario name(s) or --all")

    run_tag = args.run_tag or _now_tag()
    scenarios = _discover_scenarios(
        args.scenarios if args.scenarios else None
    )
    if not scenarios:
        print("no scenarios discovered", file=sys.stderr)
        return 1

    print(f"parallel runner: {len(scenarios)} scenario(s), "
          f"parallel={args.parallel}, run-tag={run_tag}, "
          f"timeout={args.timeout}s")
    print(f"scenarios: {', '.join(scenarios)}")

    wall_start = time.time()
    results: list[tuple[str, int, float, bool]] = []

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {
            pool.submit(_run_one, s, run_tag, args.timeout): s
            for s in scenarios
        }
        for future in as_completed(futures):
            scenario = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = (scenario, -1, 0.0, False)
                print(f"[{scenario}] worker thread exception: {exc}",
                      file=sys.stderr)
            results.append(result)
            s, rc, elapsed, to = result
            if to:
                print(f"[{s}] ⏱ timed out after {elapsed:.0f}s")
            else:
                print(f"[{s}] done rc={rc} elapsed={elapsed:.0f}s")

    _print_summary(results, run_tag, wall_start)
    _run_pattern_finder(run_tag)

    failures = sum(1 for _, rc, _, to in results if rc != 0 or to)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
