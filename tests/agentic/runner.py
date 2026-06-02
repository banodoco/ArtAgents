"""Sisypy-backed agentic test runner for Astrid.

This is the primary public entry point.  It thinly delegates to the
Sisypy CLI, using the ``AstridProjectAdapter`` from ``adapter.py``.
The legacy runner (``runner_legacy.py``) and parallel runner
(``parallel_runner.py``) were decommissioned in M5.

Usage:
    python -m tests.agentic.runner --help
    python -m tests.agentic.runner <scenario> [--actor ...] [--mode ...]
    python -m tests.agentic.runner _smoke --actor fake --mode structural

Legacy flags (``--all``, ``--tier``, ``--agent``, ``--only``,
``--timeout``, ``--budget``, ``--run-tag``) are rejected with a clear
error directing users to the Sisypy equivalents.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Legacy flags that MUST NOT leak into the Sisypy-backed runner.
# These were used by the decommissioned legacy runner (runner_legacy.py).
# ---------------------------------------------------------------------------
_LEGACY_ONLY_FLAGS: set[str] = {
    "--all",
    "--tier",
    "--agent",
    "--only",
    "--timeout",
    "--budget",
    "--run-tag",
}

_LEGACY_ALIASES: dict[str, str] = {
    "--all": "The legacy runner has been decommissioned. "
    "Omit scenario names to run all scenarios in the Sisypy runner, "
    "or use `python -m tests.agentic.runner --help`.",
    "--tier": "The legacy runner has been decommissioned. "
    "Use `--tags <tag>` in the Sisypy runner for filtering, "
    "or `python -m tests.agentic.runner --help`.",
    "--agent": "Use `--actor <dispatcher>` in the Sisypy runner (e.g. `--actor hermes`).",
    "--only": "Pass a single scenario name as a positional argument instead.",
    "--timeout": "Timeouts are managed by the Sisypy dispatcher; see Sisypy docs.",
    "--budget": "Budget is managed per-scenario via the scenario YAML.",
    "--run-tag": "Use `--tag <label>` in the Sisypy runner for report grouping.",
}

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"
BRIEFS_DIR = Path(__file__).resolve().parent / "briefs"
_STRUCTURAL_GUARD_WARNING = (
    "Structural-mode guard active: RUNPOD_API_KEY and cloud credentials stripped, "
    "no-GPU constraints enforced."
)


def _check_legacy_flags(argv: list[str]) -> None:
    """Reject any legacy-only flags with a helpful migration message."""
    for arg in argv:
        if arg in _LEGACY_ONLY_FLAGS:
            msg = _LEGACY_ALIASES.get(arg, f"Legacy flag {arg!r} is not supported.")
            print(
                f"error: {arg!r} is a legacy runner flag that is no longer supported. "
                f"The legacy runner was decommissioned in M5.\n{msg}\n"
                f"Run `python -m tests.agentic.runner --help` for supported flags.",
                file=sys.stderr,
            )
            sys.exit(2)
        # Catch --flag=value forms
        for legacy_flag in _LEGACY_ONLY_FLAGS:
            if arg.startswith(f"{legacy_flag}="):
                msg = _LEGACY_ALIASES.get(legacy_flag, f"Legacy flag {legacy_flag!r} is not supported.")
                print(
                    f"error: {arg!r} is a legacy runner flag that is no longer supported. "
                    f"The legacy runner was decommissioned in M5.\n{msg}\n"
                    f"Run `python -m tests.agentic.runner --help` for supported flags.",
                    file=sys.stderr,
                )
                sys.exit(2)


def _strip_structural_guard_warnings(result: dict[str, Any]) -> dict[str, Any]:
    """Treat structural guard notices as warnings, not run-blocking errors."""

    def _iter_runs(summary: dict[str, Any]) -> list[dict[str, Any]]:
        if "runs" in summary:
            runs = summary.get("runs", [])
            return runs if isinstance(runs, list) else []
        if "scenarios" in summary:
            out: list[dict[str, Any]] = []
            for scenario_summary in summary.get("scenarios", []):
                if isinstance(scenario_summary, dict):
                    runs = scenario_summary.get("runs", [])
                    if isinstance(runs, list):
                        out.extend(run for run in runs if isinstance(run, dict))
            return out
        if "results" in summary:
            runs = summary.get("results", [])
            return [run for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []
        return []

    runs = _iter_runs(result)
    for run in runs:
        errors = run.get("errors")
        if not isinstance(errors, list):
            continue
        remaining = [err for err in errors if err != _STRUCTURAL_GUARD_WARNING]
        removed = [err for err in errors if err == _STRUCTURAL_GUARD_WARNING]
        if removed:
            warnings = run.get("warnings")
            if not isinstance(warnings, list):
                warnings = []
            warnings.extend(removed)
            run["warnings"] = warnings
        run["errors"] = remaining

    if "has_blocked_or_error" in result:
        has_blocked_or_error = False
        if result.get("error"):
            has_blocked_or_error = True
        for run in runs:
            outcome = run.get("outcome", "")
            if outcome in ("blocked_prerequisite", "skipped_live"):
                has_blocked_or_error = True
                break
            if run.get("errors"):
                has_blocked_or_error = True
                break
        result["has_blocked_or_error"] = has_blocked_or_error

    return result


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``python -m tests.agentic.runner``.

    Delegates to ``sisypy.console_cli`` with the ``AstridProjectAdapter``
    and prints the result JSON before exiting with the computed code.
    """
    if argv is None:
        argv = sys.argv[1:]

    # --- Guard: reject legacy-only flags before Sisypy parses them ---
    _check_legacy_flags(argv)

    # --- Lazy import to keep startup fast for --help ---
    from tests.agentic.adapter import AstridProjectAdapter  # noqa: E402
    from tests.agentic.normalize import discover_scenarios, normalize_scenario  # noqa: E402

    adapter = AstridProjectAdapter()

    try:
        from sisypy import build_cli_parser, run_from_args, summary_exit_code  # noqa: E402
    except ImportError:
        print(
            "Sisypy is not importable. Install it via:\n"
            "  pip install git+https://github.com/peteromallet/sisypy.git",
            file=sys.stderr,
        )
        sys.exit(3)

    parser = build_cli_parser(adapter)
    args = parser.parse_args(argv)

    if getattr(args, "reassess", None):
        result = _strip_structural_guard_warnings(run_from_args(adapter, args))
        print(json.dumps(result, indent=2, default=str))
        sys.exit(summary_exit_code(result))

    scenarios_dir = Path(args.scenarios_dir)
    if scenarios_dir == Path("scenarios"):
        scenarios_dir = SCENARIOS_DIR

    briefs_dir = Path(args.briefs_dir)
    if briefs_dir == Path("briefs"):
        briefs_dir = BRIEFS_DIR

    selected_paths = discover_scenarios(args.scenarios, scenarios_dir=scenarios_dir)

    with tempfile.TemporaryDirectory(prefix="astrid-sisypy-") as temp_dir:
        normalized_dir = Path(temp_dir)
        for scenario_path in selected_paths:
            raw_scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
            normalized = normalize_scenario(raw_scenario)
            normalized_path = normalized_dir / scenario_path.name
            normalized_path.write_text(
                yaml.safe_dump(normalized, sort_keys=False),
                encoding="utf-8",
            )

        args.scenarios_dir = str(normalized_dir)
        args.briefs_dir = str(briefs_dir)

        result = _strip_structural_guard_warnings(run_from_args(adapter, args))
        print(json.dumps(result, indent=2, default=str))
        sys.exit(summary_exit_code(result))


if __name__ == "__main__":
    main()
