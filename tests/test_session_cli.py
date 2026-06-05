"""Direct argparse tests for ``astrid.core.session.cli``.

These tests invoke ``session_cli.main(argv=[...])`` directly — no subprocess.
Downstream handlers (cmd_attach, cmd_status, etc.) are monkeypatched at the
boundary so we exercise only the argparse glue, not session/identity I/O.

The full handler behavior is covered by ``tests/session/test_*``.
"""

from __future__ import annotations

import argparse

import pytest

from astrid.core.session import cli as session_cli


# ---------------------------------------------------------------------------
# Help and discovery
# ---------------------------------------------------------------------------


def test_help_exits_zero_and_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "python3 -m astrid sessions" in captured.out
    for sub in ("attach", "ls", "detach", "takeover", "status"):
        assert sub in captured.out


def test_attach_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main(["attach", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--timeline" in captured.out
    assert "--session" in captured.out
    assert "--default" in captured.out


def test_takeover_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main(["takeover", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--force" in captured.out


# ---------------------------------------------------------------------------
# Invalid input branches
# ---------------------------------------------------------------------------


def test_no_subcommand_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main([])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "required" in captured.err.lower() or "command" in captured.err.lower()


def test_unknown_subcommand_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main(["bogus-verb"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err.lower() or "bogus-verb" in captured.err


def test_takeover_missing_target_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main(["takeover"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "target" in captured.err.lower()
    assert "required" in captured.err.lower()


def test_attach_rejects_unknown_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main(["attach", "my-proj", "--no-such-flag"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "unrecognized" in captured.err.lower() or "--no-such-flag" in captured.err


# ---------------------------------------------------------------------------
# Valid invocations — mock handlers; assert parsed Namespace shape.
# ---------------------------------------------------------------------------


def test_attach_parses_all_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_attach(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_attach", fake_attach)

    rc = session_cli.main(
        [
            "attach",
            "my-proj",
            "--timeline",
            "main-tl",
            "--as",
            "agent:tester",
            "--default",
            "--user",
        ]
    )
    assert rc == 0
    args = seen["args"]
    assert args.command == "attach"
    assert args.project == "my-proj"
    assert args.timeline == "main-tl"
    assert args.as_agent == "agent:tester"
    assert args.set_default is True
    assert args.user_default is True


def test_attach_with_no_project_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    """project is nargs='?' — attach with no positional must still parse."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_attach(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_attach", fake_attach)

    rc = session_cli.main(["attach"])
    assert rc == 0
    assert seen["args"].project is None
    assert seen["args"].set_default is False


def test_attach_resume_session_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_attach(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_attach", fake_attach)

    rc = session_cli.main(["attach", "--session", "sess-01ABC"])
    assert rc == 0
    assert seen["args"].session == "sess-01ABC"
    assert seen["args"].project is None


def test_ls_no_args_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_ls(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_sessions_ls", fake_ls)

    rc = session_cli.main(["ls"])
    assert rc == 0
    assert seen["args"].command == "ls"


def test_detach_optional_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_detach(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_sessions_detach", fake_detach)

    # No id — should parse (nargs='?').
    rc = session_cli.main(["detach"])
    assert rc == 0
    assert seen["args"].session_id is None

    # With explicit id.
    seen.clear()
    rc = session_cli.main(["detach", "sess-XYZ"])
    assert rc == 0
    assert seen["args"].session_id == "sess-XYZ"


def test_takeover_parses_target_and_force(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_takeover(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_sessions_takeover", fake_takeover)

    rc = session_cli.main(["takeover", "run-42", "--force"])
    assert rc == 0
    assert seen["args"].target == "run-42"
    assert seen["args"].force is True


def test_status_no_args(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_status(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_status", fake_status)

    rc = session_cli.main(["status"])
    assert rc == 0
    assert seen["args"].command == "status"


# ---------------------------------------------------------------------------
# prune subcommand tests
# ---------------------------------------------------------------------------


def test_prune_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        session_cli.main(["prune", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--older-than-days" in captured.out
    assert "--apply" in captured.out


def test_prune_no_sessions(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_cli, "_list_session_files", lambda: [])
    rc = session_cli.main(["prune"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "no session records found" in captured.out


def test_prune_dry_run_default(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that prune defaults to dry-run: dispatches handler with apply=False."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_prune(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_sessions_prune", fake_prune)

    rc = session_cli.main(["prune"])
    assert rc == 0
    assert seen["args"].apply is False
    assert seen["args"].older_than_days == 30


def test_prune_apply_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --apply flag sets apply=True and dispatches handler."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_prune(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_sessions_prune", fake_prune)

    rc = session_cli.main(["prune", "--apply"])
    assert rc == 0
    assert seen["args"].apply is True


def test_prune_custom_older_than_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --older-than-days accepts custom values."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_prune(args: argparse.Namespace, *, out=None) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(session_cli, "cmd_sessions_prune", fake_prune)

    rc = session_cli.main(["prune", "--older-than-days", "7"])
    assert rc == 0
    assert seen["args"].older_than_days == 7
    assert seen["args"].apply is False
