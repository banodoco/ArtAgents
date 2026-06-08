"""T17: Preamble and gate-coverage assertions — separate from JSON verb parametrization.

Verifies:
- ``astrid next --quiet`` omits the prohibition preamble while preserving the
  actionable block (SD1).
- Default preamble bytes remain pinned (byte-snapshot).
- Parser-surface / no-raw-``sys.exit`` gates cover only the explicit in-scope
  agent-facing module list (no pack executors).
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from astrid.core.task.lifecycle import cmd_next  # noqa: E402
from astrid.core.task.preamble import PROHIBITION_PREAMBLE  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BODY_CODE = """from astrid.orchestrate import orchestrator, code
@orchestrator("demo.code")
def main(): return [code("step_a", argv=["echo", "alpha"])]
"""


def _capture_next(*argv: str, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr) for cmd_next."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_next(list(argv), projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Preamble byte-pinning
# ---------------------------------------------------------------------------

_EXPECTED_PREAMBLE = (
    "ASTRID TASK RUN — PROHIBITIONS\n"
    "- You are inside a frozen plan. Plan structure is pinned by hash; deviation "
    "from the printed step is rejected at the gate.\n"
    "- Do not edit plan.json or events.jsonl by hand. Both are append-only / "
    "immutable; tampering breaks the hash chain and aborts the run.\n"
    "- Advance only via `astrid ack` or by running the printed argv. No "
    "freelancing, no parallel commands, no re-ordering steps.\n"
    "- Use `astrid abort --project <slug>` to leave the run cleanly. Do not "
    "delete active_run.json or run directories to escape."
)


def test_default_preamble_bytes_remain_pinned() -> None:
    """PROHIBITION_PREAMBLE is a pinned contract constant — any edit must be
    deliberate and accompanied by an update to this snapshot."""
    assert PROHIBITION_PREAMBLE == _EXPECTED_PREAMBLE, (
        "PROHIBITION_PREAMBLE changed — update the snapshot if this is deliberate"
    )
    assert isinstance(PROHIBITION_PREAMBLE, str)
    assert len(PROHIBITION_PREAMBLE) > 0
    assert PROHIBITION_PREAMBLE.encode("utf-8") == _EXPECTED_PREAMBLE.encode("utf-8")


# ---------------------------------------------------------------------------
# --quiet preamble suppression (separate from JSON parametrization)
# ---------------------------------------------------------------------------


def test_next_quiet_omits_preamble_preserves_actionable_block(tmp_path: Path) -> None:
    """``astrid next --quiet`` suppresses the preamble/separator but keeps the
    actionable prose identical to the default-mode prose after the preamble."""
    from _lifecycle_fixtures import setup_run  # noqa: E402

    packs, projects = setup_run(
        tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r-quiet"
    )

    # Capture default and quiet outputs from separate fresh calls.
    rc_d, stdout_d, stderr_d = _capture_next("--project", "p", projects=projects)
    rc_q, stdout_q, stderr_q = _capture_next(
        "--project", "p", "--quiet", projects=projects
    )

    assert rc_d == 0, f"default rc={rc_d} stderr={stderr_d!r}"
    assert rc_q == 0, f"quiet rc={rc_q} stderr={stderr_q!r}"

    # Default must include the preamble.
    assert PROHIBITION_PREAMBLE in stdout_d, "default must include preamble"

    # Quiet must NOT include the preamble.
    assert PROHIBITION_PREAMBLE not in stdout_q, (
        f"quiet must not include preamble: {stdout_q!r}"
    )

    # Quiet output must be non-empty (actionable prose preserved).
    assert stdout_q.strip(), "quiet output must contain actionable prose"

    # The prose after the preamble+separator in default mode must match the
    # quiet output byte-for-byte.
    preamble_line_count = PROHIBITION_PREAMBLE.count("\n") + 1
    default_lines = stdout_d.splitlines(keepends=True)
    # Default output structure: [preamble lines...] + [blank separator line] + [prose...]
    default_prose = "".join(default_lines[preamble_line_count + 1:])
    assert default_prose == stdout_q, (
        f"prose mismatch after preamble suppression:\n"
        f"--- DEFAULT PROSE ---\n{default_prose!r}\n"
        f"--- QUIET OUTPUT ---\n{stdout_q!r}"
    )


def test_next_default_mode_includes_preamble_on_stdout(tmp_path: Path) -> None:
    """Default ``astrid next`` prints the preamble verbatim to stdout."""
    from _lifecycle_fixtures import setup_run  # noqa: E402

    packs, projects = setup_run(
        tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r-def"
    )

    rc, stdout, stderr = _capture_next("--project", "p", projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"

    assert PROHIBITION_PREAMBLE in stdout, (
        "preamble must appear on stdout in default mode"
    )

    # Preamble is followed by a blank separator line.
    preamble_pos = stdout.index(PROHIBITION_PREAMBLE)
    after_preamble = stdout[preamble_pos + len(PROHIBITION_PREAMBLE):]
    assert after_preamble.startswith("\n"), (
        "preamble must be followed by separator newline"
    )

    # Actionable prose must follow the preamble+separator.
    actionable = after_preamble.lstrip("\n")
    assert len(actionable) > 0, "no actionable prose after preamble"


# ---------------------------------------------------------------------------
# Gate coverage — explicit in-scope agent-facing module list
# ---------------------------------------------------------------------------

_EXPECTED_AGENT_CLI_MODULES: set[str] = {
    "astrid/gateway/__init__.py",
    "astrid/gateway/dispatch.py",
    "astrid/core/session/cli.py",
    "astrid/core/task/claim.py",
    "astrid/core/task/lifecycle.py",
    "astrid/core/task/lifecycle_ack.py",
    "astrid/core/task/lifecycle_skip.py",
    "astrid/core/task/operator_view.py",
    "astrid/core/task/run_store.py",
    "astrid/core/task/plan_builder.py",
    "astrid/core/task/cli_contract.py",
    "astrid/core/task/gate_base.py",
}

# Known pack executor paths that must NOT appear in the agent-facing list.
_EXCLUDED_PREFIXES: tuple[str, ...] = (
    "astrid/core/executor/",
    "astrid/packs/",
)


def test_agent_cli_module_paths_covers_only_explicit_in_scope_list() -> None:
    """AGENT_CLI_MODULE_PATHS contains exactly the expected set of agent-facing
    CLI modules and excludes pack executor surfaces."""
    from test_recovery_command_conformance import AGENT_CLI_MODULE_PATHS  # noqa: E402

    ROOT = Path(__file__).resolve().parents[1]
    actual: set[str] = {
        str(p.relative_to(ROOT)) for p in AGENT_CLI_MODULE_PATHS
    }

    # 1. Every expected module is present.
    missing = _EXPECTED_AGENT_CLI_MODULES - actual
    assert not missing, (
        f"AGENT_CLI_MODULE_PATHS is missing expected modules: {sorted(missing)}"
    )

    # 2. No unexpected extra modules.
    extra = actual - _EXPECTED_AGENT_CLI_MODULES
    assert not extra, (
        f"AGENT_CLI_MODULE_PATHS has extra unexpected modules: {sorted(extra)}"
    )

    # 3. No pack executor paths leaked in.
    for p in AGENT_CLI_MODULE_PATHS:
        rel = str(p.relative_to(ROOT))
        assert not rel.startswith(_EXCLUDED_PREFIXES), (
            f"Pack executor path leaked into AGENT_CLI_MODULE_PATHS: {rel}"
        )

    # 4. Every listed path exists on disk.
    for p in AGENT_CLI_MODULE_PATHS:
        assert p.is_file(), f"AGENT_CLI_MODULE_PATHS entry does not exist: {p}"


def test_no_raw_sys_exit_in_agent_cli_modules_outside_main_guards() -> None:
    """No raw ``sys.exit(...)`` outside ``if __name__ == '__main__'`` guards
    in the explicit agent-facing CLI modules."""
    import ast

    from test_recovery_command_conformance import (  # noqa: E402
        AGENT_CLI_MODULE_PATHS,
        _build_parents,
        _inside_if_name_main,
    )

    ROOT = Path(__file__).resolve().parents[1]
    failures: dict[str, list[int]] = {}

    for path in AGENT_CLI_MODULE_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = _build_parents(tree)
        findings: list[int] = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "exit"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
            ):
                continue
            if not _inside_if_name_main(node, parents):
                findings.append(node.lineno)
        if findings:
            failures[str(path.relative_to(ROOT))] = findings

    assert not failures, (
        "Agent CLI modules have raw sys.exit outside __main__ guards:\n"
        + "\n".join(f"  {p}: lines {lines}" for p, lines in failures.items())
    )


def test_recovery_commands_cover_only_agent_facing_surface() -> None:
    """Every recovery command extracted from AGENT_CLI_MODULE_PATHS parses cleanly
    and is scoped to the explicit in-scope agent-facing surface."""
    from test_recovery_command_conformance import (  # noqa: E402
        AGENT_CLI_MODULE_PATHS,
        _assert_recovery_command_parses,
        _extract_recovery_commands,
    )

    all_commands: list[str] = []
    for path in AGENT_CLI_MODULE_PATHS:
        all_commands.extend(_extract_recovery_commands(path))

    assert all_commands, (
        "No recovery commands found — extraction may be missing patterns"
    )

    failures: list[tuple[str, str]] = []
    for command in sorted(set(all_commands)):
        try:
            _assert_recovery_command_parses(command)
        except (AssertionError, ValueError) as exc:
            failures.append((command, str(exc)))

    assert not failures, (
        "Recovery commands failed to parse:\n"
        + "\n".join(f"  {cmd!r}: {err}" for cmd, err in failures)
    )
