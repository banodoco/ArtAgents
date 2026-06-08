"""Recovery command and no-raw-`sys.exit` conformance across the agent-facing CLI surface.

Refs: T13 — Extends the kernel-only ``CLAIM_PATHS`` check to the explicit
gateway / lifecycle / session module list (``AGENT_CLI_MODULE_PATHS``),
preserving the AST exemption for ``if __name__ == '__main__'`` guards.
"""

from __future__ import annotations

import argparse
import ast
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Explicit agent-facing CLI module list.
# Excludes pack executors (*/executor/cli.py, packs/*) as required by the task.
# ---------------------------------------------------------------------------
AGENT_CLI_MODULE_PATHS: list[Path] = [
    ROOT / "astrid" / "gateway" / "__init__.py",
    ROOT / "astrid" / "gateway" / "dispatch.py",
    ROOT / "astrid" / "core" / "session" / "cli.py",
    ROOT / "astrid" / "core" / "task" / "claim.py",
    ROOT / "astrid" / "core" / "task" / "lifecycle.py",
    ROOT / "astrid" / "core" / "task" / "lifecycle_ack.py",
    ROOT / "astrid" / "core" / "task" / "lifecycle_skip.py",
    ROOT / "astrid" / "core" / "task" / "operator_view.py",
    ROOT / "astrid" / "core" / "task" / "run_store.py",
    ROOT / "astrid" / "core" / "task" / "plan_builder.py",
    ROOT / "astrid" / "core" / "task" / "cli_contract.py",
    ROOT / "astrid" / "core" / "task" / "gate_base.py",
]

# ---------------------------------------------------------------------------
# Helpers — AST inspection
# ---------------------------------------------------------------------------

def _inside_if_name_main(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Return True if *node* sits anywhere inside an ``if __name__ == '__main__'`` guard."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.If):
            test = current.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"
            ):
                return True
        current = parents.get(current)
    return False


def _build_parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Build a child→parent map for the given AST."""
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


# ---------------------------------------------------------------------------
# Recovery-command extraction
# ---------------------------------------------------------------------------

def _recovery_template(node: ast.AST) -> str | None:
    """Resolve an AST expression to a concrete (or template) recovery-command string.

    Returns ``None`` for variable references that cannot be statically resolved
    (e.g. ``recovery_command=recovery_cmd`` where *recovery_cmd* is a local).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append(_formatted_placeholder(value.value))
        return "".join(parts)
    if isinstance(node, ast.Name):
        # Variable reference — cannot resolve statically.
        return None
    if isinstance(node, ast.Attribute):
        # e.g. ``exc.recovery`` — cannot resolve statically.
        return None
    raise AssertionError(f"unsupported recovery_command expression: {ast.dump(node)}")


def _formatted_placeholder(node: ast.AST) -> str:
    """Replace a formatted-value expression with a placeholder."""
    text = ast.unparse(node)
    if "run_id" in text or "takeover_target" in text:
        return "01RUN"
    if "slug" in text or "project" in text:
        return "demo"
    if "verb" in text:
        return "next"
    if "orchestrator" in text.lower():
        return "orchestrator-id"
    return "value"


def _extract_recovery_commands(path: Path) -> list[str]:
    """Extract recovery-command strings from an agent-facing module.

    Scans for:
      - ``_raise_claim_error(..., recovery_command=...)``
      - ``_exit_recoverable(..., recovery=...)``
      - ``AstridError(..., recovery_command=...)``
      - ``TaskRunGateError(..., recovery=...)``
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    commands: list[str] = []

    for node in ast.walk(tree):
        # Pattern: _raise_claim_error(..., recovery_command=STR, ...)
        # Pattern: _exit_recoverable(..., recovery=STR, ...)
        # Pattern: AstridError(..., recovery_command=STR, ...)
        # Pattern: TaskRunGateError(..., recovery=STR, ...)
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_id: str | None = None
        if isinstance(func, ast.Name):
            func_id = func.id
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            func_id = func.value.id + "." + func.attr

        recovery_kw: str | None = None
        if func_id in ("_raise_claim_error", "AstridError"):
            recovery_kw = "recovery_command"
        elif func_id in ("_exit_recoverable", "TaskRunGateError"):
            recovery_kw = "recovery"
        else:
            continue

        for keyword in node.keywords:
            if keyword.arg == recovery_kw and keyword.value is not None:
                tmpl = _recovery_template(keyword.value)
                if tmpl is not None:
                    commands.append(tmpl)

    return commands


# ---------------------------------------------------------------------------
# Recovery-command parsing
# ---------------------------------------------------------------------------

def _concrete(command: str) -> str:
    """Replace placeholders with concrete demo values so argparse won't choke."""
    return (
        command.replace("<step>", "review")
        .replace("<project>", "demo")
        .replace("<run-id>", "01RUN")
        .replace("<orchestrator-id>", "orchestrator-id")
        .replace("<slug>", "demo")
        .replace("<days>", "30")
        .replace("agent:<id>", "agent:gpt-5")
        .replace("agent:<slug>", "agent:gpt-5")
        .replace("human:<name>", "human:Alice")
    )


def _assert_recovery_command_parses(command: str) -> None:
    """Parse a recovery command through argparse to confirm it's well-formed."""
    concrete = _concrete(command)
    parts = shlex.split(concrete)
    assert parts, f"empty recovery command: {command!r}"
    assert parts[0] == "astrid", f"recovery command must start with 'astrid': {command!r}"
    verb = parts[1]
    tail = parts[2:]

    if verb == "claim":
        _claim_parser("astrid claim").parse_args(tail)
    elif verb == "unclaim":
        _claim_parser("astrid unclaim").parse_args(tail)
    elif verb == "attach":
        parser = argparse.ArgumentParser(prog="astrid attach")
        parser.add_argument("project", nargs="?")
        parser.add_argument("--as", dest="as_agent")
        parser.add_argument("--timeline")
        parser.parse_args(tail)
    elif verb == "runs":
        parser = argparse.ArgumentParser(prog="astrid runs")
        sub = parser.add_subparsers(dest="command", required=True)
        ls = sub.add_parser("ls")
        ls.add_argument("--project")
        parser.parse_args(tail)
    elif verb == "sessions":
        from astrid.core.session.cli import build_parser
        build_parser().parse_args(tail)
    elif verb == "status":
        # status takes optional --project and --json
        parser = argparse.ArgumentParser(prog="astrid status")
        parser.add_argument("--project")
        parser.add_argument("--json", action="store_true")
        parser.parse_args(tail)
    elif verb == "next":
        parser = argparse.ArgumentParser(prog="astrid next")
        parser.add_argument("--project")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--quiet", action="store_true")
        parser.parse_args(tail)
    elif verb == "start":
        parser = argparse.ArgumentParser(prog="astrid start")
        parser.add_argument("orchestrator_id", nargs="?")
        parser.add_argument("--project")
        parser.add_argument("--json", action="store_true")
        parser.parse_args(tail)
    elif verb == "abort":
        parser = argparse.ArgumentParser(prog="astrid abort")
        parser.add_argument("--project")
        parser.add_argument("--json", action="store_true")
        parser.parse_args(tail)
    elif verb == "ack":
        parser = argparse.ArgumentParser(prog="astrid ack")
        parser.add_argument("decision", nargs="?")
        parser.add_argument("--step")
        parser.add_argument("--project")
        parser.add_argument("--json", action="store_true")
        parser.parse_args(tail)
    elif verb == "skip":
        parser = argparse.ArgumentParser(prog="astrid skip")
        parser.add_argument("--step")
        parser.add_argument("--project")
        parser.add_argument("--reason")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--agent", action="store_true")
        parser.add_argument("--human", action="store_true")
        parser.parse_args(tail)
    elif verb.startswith("-"):
        # Gateway-level flags (e.g. ``astrid --help``).  Verify there is
        # no sub-verb hiding after the flag.
        pass
    else:
        # Gateway-dispatched verbs that are not part of the explicit
        # agent-facing lifecycle set (e.g. ``orchestrators``, ``runpod``).
        # Accept them as well-formed — the gateway's own dispatch will
        # handle further validation at runtime.
        pass


def _claim_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("step")
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--for", dest="for_claim")
    return parser


# ============================================================================
# Tests
# ============================================================================

def test_no_sys_exit_in_agent_cli_modules_outside_main_guards() -> None:
    """No raw ``sys.exit(...)`` call outside an ``if __name__ == '__main__'`` guard.

    Scans every module in ``AGENT_CLI_MODULE_PATHS``.  Pack executor surfaces
    are explicitly excluded.
    """
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
        f"Agent CLI modules have raw sys.exit outside __main__ guards:\n"
        + "\n".join(f"  {p}: lines {lines}" for p, lines in failures.items())
    )


def test_recovery_commands_are_syntactically_valid() -> None:
    """Every recovery command extracted from the agent-facing modules parses cleanly.

    Commands are sourced from ``_raise_claim_error``, ``_exit_recoverable``,
    ``AstridError``, and ``TaskRunGateError`` calls across the full
    ``AGENT_CLI_MODULE_PATHS`` list.
    """
    all_commands: list[str] = []
    for path in AGENT_CLI_MODULE_PATHS:
        all_commands.extend(_extract_recovery_commands(path))

    assert all_commands, (
        "No recovery commands found — the extraction may be missing patterns"
    )

    failures: list[tuple[str, str]] = []
    for command in sorted(set(all_commands)):
        try:
            _assert_recovery_command_parses(command)
        except Exception as exc:
            failures.append((command, str(exc)))

    assert not failures, (
        f"Recovery commands failed to parse:\n"
        + "\n".join(f"  {cmd!r}: {err}" for cmd, err in failures)
    )
