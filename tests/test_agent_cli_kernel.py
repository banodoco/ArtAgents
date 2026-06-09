"""Agent CLI kernel conformance tests."""

from __future__ import annotations

import argparse
import ast
import io
import json
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import bind_writer_session, setup_run  # noqa: E402

from astrid.core.project.project import create_project
from astrid.core.task.lifecycle import cmd_next, cmd_runs_ls
from astrid.core.timeline.crud import create_timeline


ROOT = Path(__file__).resolve().parents[1]
CLAIM_PATHS = [ROOT / "astrid" / "core" / "task" / "claim.py"]
NEXT_JSON_KEYS = {
    "schema_version",
    "project",
    "run_id",
    "state",
    "action",
    "command",
    "step",
    "blocked",
    "reason",
}

_BODY_CODE = '''from astrid.core.orchestrate import orchestrator, code
@orchestrator("demo.code")
def main(): return [code("step_a", argv=["echo", "alpha"])]
'''


def _capture_next_json(argv: list[str], projects: Path) -> tuple[dict[str, object], str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_next([*argv, "--json"], projects_root=projects)
    assert rc == 0, err.getvalue()
    stdout = out.getvalue()
    assert stdout.count("\n") == 1
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    assert set(payload) == NEXT_JSON_KEYS
    return payload, stdout


def test_next_json_no_active_run_emits_single_schema_object(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    projects.mkdir()
    create_project("p", root=projects, exist_ok=True)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    payload, stdout = _capture_next_json(["--project", "p"], projects)

    assert json.loads(stdout) == payload
    assert payload["project"] == "p"
    assert payload["run_id"] is None
    assert payload["state"] == "no_active_run"
    assert payload["action"] == "start"
    assert payload["command"] == "astrid start <orchestrator-id> --project p"
    assert payload["blocked"] is False


def test_next_json_active_step_emits_command_only(tmp_path: Path) -> None:
    _packs, projects = setup_run(
        tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="r-json"
    )

    payload, stdout = _capture_next_json(["--project", "p"], projects)

    assert json.loads(stdout) == payload
    assert payload["project"] == "p"
    assert payload["run_id"] == "r-json"
    assert payload["state"] == "ready"
    assert payload["action"] == "run"
    assert payload["step"] == "step_a"
    assert isinstance(payload["command"], str)
    assert payload["command"].startswith("ASTRID_INTERNAL_INVOCATION=1 ")
    assert "echo alpha" in payload["command"]
    assert payload["blocked"] is False


def test_runs_ls_json_emits_valid_array(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    run_dir = projects / "p" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "run_started", "run_id": "run-1", "ts": "2026-06-04T00:00:00Z"})
        + "\n",
        encoding="utf-8",
    )

    out = io.StringIO()
    with redirect_stdout(out):
        rc = cmd_runs_ls(["--project", "p", "--json"], projects_root=projects)

    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload == [
        {
            "run_id": "run-1",
            "status": "in-flight",
            "started_at": "2026-06-04T00:00:00Z",
            "summary": "run_started",
        }
    ]


def test_no_sys_exit_in_claim_py_outside_main_guards() -> None:
    for path in CLAIM_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
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
        assert not findings, f"{path.relative_to(ROOT)} has sys.exit at lines {findings}"


def test_claim_recovery_commands_are_syntactically_valid() -> None:
    source = CLAIM_PATHS[0].read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CLAIM_PATHS[0]))
    commands: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_raise_claim_error"
        ):
            continue
        for keyword in node.keywords:
            if keyword.arg == "recovery_command":
                commands.append(_recovery_template(keyword.value))
    assert commands
    for command in commands:
        _assert_recovery_command_parses(command)


def _inside_if_name_main(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
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


def _recovery_template(node: ast.AST) -> str:
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
    raise AssertionError(f"unsupported recovery_command expression: {ast.dump(node)}")


def _formatted_placeholder(node: ast.AST) -> str:
    text = ast.unparse(node)
    if "run_id" in text or "takeover_target" in text:
        return "01RUN"
    if "slug" in text or "project" in text:
        return "demo"
    return "value"


def _assert_recovery_command_parses(command: str) -> None:
    concrete = (
        command.replace("<step>", "review")
        .replace("<project>", "demo")
        .replace("<run-id>", "01RUN")
        .replace("agent:<id>", "agent:gpt-5")
        .replace("human:<name>", "human:Alice")
    )
    parts = shlex.split(concrete)
    assert parts[0] == "astrid"
    verb = parts[1]
    tail = parts[2:]
    if verb == "claim":
        _claim_parser("astrid claim").parse_args(tail)
    elif verb == "unclaim":
        _claim_parser("astrid unclaim").parse_args(tail)
    elif verb == "attach":
        parser = argparse.ArgumentParser(prog="astrid attach")
        parser.add_argument("project", nargs="?")
        parser.parse_args(tail)
    elif verb == "runs":
        parser = argparse.ArgumentParser(prog="astrid runs")
        sub = parser.add_subparsers(dest="command", required=True)
        ls = sub.add_parser("ls")
        ls.add_argument("--project")
        parser.parse_args(tail)
    elif verb == "sessions":
        from astrid.core.cli.session import build_parser

        build_parser().parse_args(tail)
    else:
        raise AssertionError(f"unknown recovery verb in {command!r}")


def _claim_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("step")
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--for", dest="for_claim")
    return parser
